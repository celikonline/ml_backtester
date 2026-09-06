import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from backend.engine import demo_prices
from backend.platform.indicators import indicator_frame, cached_indicators, rule_masks, apply_rules
from backend.platform.research import execute_research, feature_frame, optimize
from backend.platform.schema import ExperimentSpec, SignalRules, candidate_count


def test_indicators_are_causal():
    df = demo_prices(600)
    expected = indicator_frame(df).iloc[:400]
    changed = df.copy()
    changed.iloc[400:] *= 2
    pd.testing.assert_frame_equal(expected, indicator_frame(changed).iloc[:400])


def test_indicator_cache_reuse_and_data_invalidation(tmp_path):
    df=demo_prices(500)
    first=cached_indicators(df,tmp_path)
    assert len(list(tmp_path.glob('*.npz')))==1
    pd.testing.assert_frame_equal(first,cached_indicators(df,tmp_path))
    assert len(list(tmp_path.glob('*.npz')))==1
    changed=df.copy()
    changed.loc[changed.index[-1],'close'] *= 1.01
    second=cached_indicators(changed,tmp_path)
    assert len(list(tmp_path.glob('*.npz')))==2
    assert not first.iloc[-1].equals(second.iloc[-1])


def test_crossing_rules_and_empty_side():
    rules = SignalRules(long=[dict(feature='rsi_14', operator='cross_above', value=50)])
    frame = pd.DataFrame({'rsi_14': [49., 51., 52., np.nan]})
    actual = apply_rules(np.array([1., 1., 1., -1.]), rule_masks(frame, rules))
    np.testing.assert_array_equal(actual, [0, 1, 0, -1])


@pytest.mark.parametrize('algorithm', ['random', 'grid'])
def test_search_evaluates_real_candidates(algorithm):
    df = demo_prices(650)
    x = feature_frame(df)[['rsi_14', 'ema_21', 'atr_14']].iloc[:-2]
    y = (df.open.shift(-2)/df.open.shift(-1)-1).reindex(x.index).to_numpy()
    spec = ExperimentSpec(models=['ridge'], validation={'method':'holdout'},
        optimization={'algorithm':algorithm,'population':4,'generations':1,'max_drawdown':1,'thresholds_bps':[0,1]})
    result = optimize(x,y,spec,1560,lambda *args:None)
    assert result['candidates']
    assert all(c['folds'] for c in result['candidates'])
    assert len(result['candidates']) <= candidate_count(spec)
    if algorithm == 'grid': assert len(result['candidates']) == 6


def test_end_to_end_date_bounds(tmp_path):
    df = demo_prices(900)
    spec = ExperimentSpec(models=['ridge'], period={'start':str(df.index[100].date()),
        'end':str(df.index[800].date()),'test_start':str(df.index[650].date())},
        features={'names':['rsi_14','ema_21','atr_14']},
        validation={'method':'holdout'}, optimization={'algorithm':'grid','thresholds_bps':[0],'max_drawdown':1})
    result = execute_research(df,spec,lambda *args:None,tmp_path)
    assert pd.Timestamp(result['split']['test_start']) >= pd.Timestamp(spec.period.test_start,tz='UTC')
    assert pd.Timestamp(result['split']['test_end']) < pd.Timestamp(spec.period.end,tz='UTC')+pd.Timedelta(days=1)
    assert (tmp_path/'model.joblib').exists()
    assert (tmp_path/'frozen_candidate.json').exists()


def test_regime_routing_trains_specialists_without_test_access(tmp_path):
    df = demo_prices(900)
    spec = ExperimentSpec(models=['ridge', 'random_forest'],
        features={'names':['rsi_14','ema_21','atr_14']},
        validation={'method':'holdout'},
        optimization={'algorithm':'none','max_drawdown':1},
        regime_routing={'enabled':True,'fallback_model':'ridge','min_regime_bars':15,
                        'assignments':{'0':'ridge','1':'random_forest','2':'ridge'}})
    result = execute_research(df, spec, lambda *args:None, tmp_path)
    routing = result['routing']
    assert routing['enabled'] is True
    assert result['selected_model'] == 'regime_router'
    assert result['test_policy']['candidate_frozen_before_test'] is True
    assert all(item['train_bars'] >= 0 for item in routing['specialists'])
    assert set(routing['assignments']) == {'0','1','2'}


@pytest.mark.parametrize('changes', [
    {'period':{'start':'2025-02-30'}},
    {'period':{'start':'2025-06-01','end':'2025-01-01'}},
    {'validation':{'train_ratio':.75,'validation_ratio':.4}},
    {'signal_rules':{'long':[{'feature':'rsi','operator':'eval','value':0}]}}
])
def test_invalid_configuration_rejected(changes):
    with pytest.raises(ValidationError): ExperimentSpec(**changes)


def test_preview_endpoint(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.platform.api import router, actor
    from backend.platform import db
    monkeypatch.setattr(db,'STORAGE',tmp_path)
    app=FastAPI()
    app.dependency_overrides[actor]=lambda:{'id':'tester'}
    app.include_router(router(lambda _: (demo_prices(700),'demo',True),lambda:[]))
    client=TestClient(app)
    response=client.post('/api/v1/backtest-preview',json={'dataset_id':'demo'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['rows']>0
    assert 'rsi_14' in {f['id'] for f in result['features']}
    assert list((tmp_path/'feature_cache').glob('*.npz'))
