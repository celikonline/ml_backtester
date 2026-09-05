import sys
from sqlalchemy import select, update
from .db import runs
from .schema import ExperimentSpec
from .service import ExperimentService, atomic_json, runtime_metadata
from .research import execute_research


def main(run_id):
    service=ExperimentService(initialize=False)
    try:
        with service.engine.begin() as con:
            run=con.execute(select(runs).where(runs.c.id==run_id)).mappings().one()
            con.execute(update(runs).where(runs.c.id==run_id).values(runtime={**run["runtime"],**runtime_metadata()}))
        item=service.get(run["experiment_id"])
        spec=ExperimentSpec.model_validate(item["specification"])
        df=service.load_snapshot(item["snapshot_id"])
        folder=service.storage/"runs"/run_id
        folder.mkdir(parents=True,exist_ok=True)
        atomic_json(folder/"specification.json",item["specification"])
        # execute_research keeps the holdout opaque until it emits the frozen-candidate boundary.
        opened = False
        def emit(kind, payload):
            nonlocal opened
            if kind == "candidate.frozen" and not opened:
                service.open_final_test(run_id); opened = True
            service.emit(run_id, kind, payload)
        result=execute_research(df,spec,emit,folder)
        pareto={candidate["id"] for candidate in result["optimization"]["pareto"]}
        candidates=[{**candidate,"pareto":candidate["id"] in pareto,"selected":candidate["id"]==result["optimization"]["best"]["id"]} for candidate in result["optimization"]["candidates"]]
        service.persist_candidates(item["id"],candidates,"frozen_candidate.json")
        service.persist_feature_analysis(item["id"],result["feature_analysis"],result["selected_features"],result["optimization"]["survival"])
        atomic_json(folder/"result.json",result)
        service.finish(run_id,"COMPLETED","Deney tamamlandı",str((folder/"result.json").relative_to(service.storage)),result["metrics"])
    except InterruptedError:
        service.finish(run_id,"CANCELLED","İptal edildi")
    except Exception as exc:
        service.finish(run_id,"FAILED",str(exc))
        raise
    finally: service.engine.dispose()

if __name__=="__main__": main(sys.argv[1])
