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
        result=execute_research(df,spec,lambda kind,payload:service.emit(run_id,kind,payload),folder)
        atomic_json(folder/"result.json",result)
        service.finish(run_id,"COMPLETED","Deney tamamlandı",str((folder/"result.json").relative_to(service.storage)),result["metrics"])
    except InterruptedError:
        service.finish(run_id,"CANCELLED","İptal edildi")
    except Exception as exc:
        service.finish(run_id,"FAILED",str(exc))
        raise
    finally: service.engine.dispose()

if __name__=="__main__": main(sys.argv[1])
