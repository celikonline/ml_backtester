import { getStoredWorkspaceId } from './ws-store';
// Keep the platform client aligned with the auth provider's storage contract.
// The old key made login appear successful while /api/v1 requests had no token.
export const token=()=>{
  try {
    return localStorage.getItem('regimelab.token') || sessionStorage.getItem('regimelab.token') || '';
  } catch {
    return '';
  }
};
export const lang=()=>{try{const v=localStorage.getItem('regimelab.lang');return v==='en'?'en':'tr';}catch{return 'tr';}};
export const workspaceId=()=>getStoredWorkspaceId()||'';
export const headers=()=>({'Content-Type':'application/json','X-RegimeLab-Source':'WEB','Accept-Language':lang(),...(workspaceId()?{'X-Workspace-Id':workspaceId()}:{}),...(token()?{Authorization:`Bearer ${token()}`}:{})});
export async function request<T>(path:string,method='GET',body?:unknown,extra?:Record<string,string>):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{method,headers:{...headers(),...extra},body:body===undefined?undefined:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:value.error?.message||JSON.stringify(value.detail||value));
  return value;
}
export async function download(path:string,name:string){
  const response=await fetch(`/api/v1${path}`,{headers:headers()});
  if(!response.ok)throw new Error('Dosya indirilemedi.');
  const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);
}
// ---- Quant Lab: backend/quant endpoints live under /api (not /api/v1) ----
export type QuantEnvelope<T>={success:boolean;experiment_id:string|null;data:T|null;error:string|null};
export async function requestQuant<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const response=await fetch(`/api${path}`,{method,headers:headers(),body:body===undefined?undefined:JSON.stringify(body)});
  const value=await response.json() as QuantEnvelope<T>;
  if(!response.ok||!value.success)throw new Error(value.error||'Quant isteği başarısız.');
  return value.data as T;
}
export type QuantICRow={feature:string;ic:number;abs_ic:number;sample_count:number};
export type QuantICDecayRow={feature:string;horizon:number;ic:number;sample_count:number};
export type QuantQualityRow={feature:string;ic:number;abs_ic:number;sign_consistency:number;stability_score:number;quality_score:number;cluster?:string;selected?:boolean};
export type QuantQuality={quality:QuantQualityRow[];clusters:Record<string,string[]>;selected:string[]};
export type QuantFold={train:number[];validation:number[]};
export type QuantStressRow={scenario?:string;slippage_bps?:number;latency_bars?:number;total_return:number;sharpe:number;max_drawdown:number;trade_count:number};
export type QuantStress={scenarios:QuantStressRow[];sharpe_matrix:Record<string,Record<string,number>>;base:QuantStressRow;worst:QuantStressRow};
export type QuantCalibration={calibrated_probability:number[];brier_raw:number;log_loss_raw:number;brier_calibrated?:number;log_loss_calibrated?:number;curve_raw:{prob_true:number[];prob_pred:number[]};curve_calibrated?:{prob_true:number[];prob_pred:number[]}};
export type QuantFitness={fitness:number;breakdown:{sharpe_contribution:number;feature_quality_contribution:number;drawdown_penalty:number;turnover_penalty:number}};
export type QuantQuantile={quantiles:number[];predictions:Record<string,number>[]};
export type Spec={schema_version:'1.0';name:string;description:string;tags:string[];market:'FX';symbol:'EURUSD';dataset_id:string;timeframe:string;features:{groups:string[];families:string[];names:string[]};models:string[];optimization:{algorithm:string;population:number;generations:number;mutation_rate:number;crossover_rate:number;elitism:number;min_features:number;max_features:number;hyperparameters:boolean;objective:string;max_drawdown:number;min_trades:number;max_exposure:number|null;max_worst_regime_drawdown:number|null;thresholds_bps?:number[]};validation:{method:string;train_ratio:number;folds:number;gap:number;locked_test:true;purge_window:number;embargo_pct:number;train_window:number;test_window:number;step:number};backtest:{capital:number;cost_bps:number;slippage_bps:number};seed:number;regime_states:number;search_space_id?:string|null};
export const defaultSpec:Spec={schema_version:'1.0',name:'EURUSD araştırması',description:'',tags:[],market:'FX',symbol:'EURUSD',dataset_id:'demo',timeframe:'native',features:{groups:['technical'],families:[],names:[]},models:['ridge','xgboost'],optimization:{algorithm:'genetic',population:8,generations:4,mutation_rate:.12,crossover_rate:.8,elitism:2,min_features:3,max_features:30,hyperparameters:true,objective:'sharpe',max_drawdown:.5,min_trades:0,max_exposure:null,max_worst_regime_drawdown:null},validation:{method:'walk_forward',train_ratio:.65,folds:3,gap:2,locked_test:true,purge_window:5,embargo_pct:.01,train_window:500,test_window:50,step:50},backtest:{capital:10000,cost_bps:.5,slippage_bps:.2},seed:42,regime_states:3,search_space_id:null};
export type SearchSpaceDef={name:string;description:string;feature_groups:string[];features:string[];min_features:number;max_features:number;models:string[];hyperparameters:boolean;thresholds_bps:number[];regime_states:number;max_drawdown:number};
export type SearchSpace={id:string;name:string;version:number;definition:SearchSpaceDef;owner:string;created_at:string;archived_at:string|null;workspace_id:string|null};
export type Metric={sharpe:number;return:number;max_drawdown:number;sortino:number;position_changes:number;win_rate:number;turnover:number};
export type Experiment={id:string;code:string;name:string;parent_id:string|null;status:string;created_at:string;specification:Spec;snapshot:{id:string;sha256:string;details:{name:string;rows:number;demo:boolean;start:string;end:string;point_in_time:string;[key:string]:unknown}};run:null|{id:string;status:string;progress:number;message:string;metrics:Metric|null;duration_seconds:number|null}};
export type Curve={timestamp:string;equity:number;benchmark:number;drawdown:number;return:number;signal:number;prediction_bps:number};
export type Candidate={id:string;model:string;features:string[];parameters:Record<string,number>;metrics:Metric;fitness:number;feasible:boolean;threshold_bps:number;objectives?:Record<string,number>;regime_metrics?:{regime:number;bars:number;share:number;sharpe:number;return:number;max_drawdown:number;qualified:boolean}[];worst_regime_drawdown?:number|null;regime_coverage?:number;folds:({train_end:string;validation_start:string;validation_end:string;gap_bars:number}&Metric)[]};
export type Generation={generation:number;total_generations:number;best_fitness:number;mean_fitness:number;diversity:number;candidate_count:number;best:Candidate};
export type Optimization={best:Candidate;candidates:Candidate[];generations:Generation[];pareto:Candidate[];survival:{feature:string;selection_frequency:number;top_survival:number;fitness_present:number|null;fitness_absent:number|null}[]};
export type DbCandidate={id:string;experiment_id:string;candidate_key:string;generation:number|null;genome:Record<string,unknown>;metrics:Metric;fitness:number;pareto_rank:number|null;dominance_count:number;decision:string;artifact_ref:string|null;created_at:string;parents:string[]};
export type DbStabilityRun={id:string;window_index:number;rolling_ic:number};
export type DbRegimeMetric={id:number;regime:number;bars:number;share:number;ic:number};
export type DbFeatureEvaluation={id:string;experiment_id:string;feature:string;ic:number;sign_consistency:number;mutual_information:number;missingness:number;selected:number;created_at:string;stability_runs:DbStabilityRun[];regime_metrics:DbRegimeMetric[];selection_frequency:number|null;top_survival:number|null;fitness_present:number|null;fitness_absent:number|null};
export type FeatureIntelligence={experiment_id:string;evaluations:DbFeatureEvaluation[];redundancy_pairs:{id:number;a:string;b:string;correlation:number}[]};
export type Result={metrics:Metric;validation_metrics:Metric;validation_test_sharpe_delta:number;curve:Curve[];selected_model:string;selected_features:string[];parameters:Record<string,number>;optimization:Optimization;warnings:string[];split:{development:number;test:number;gap:number;test_start:string;test_end:string};feature_analysis:{features:{feature:string;ic:number;rolling_ic:number[];sign_consistency:number;mutual_information:number}[];redundancy_pairs:{a:string;b:string;correlation:number}[]};regimes:{id:number;bars:number;share:number;mean_net_return_bps:number|null}[];cost_sensitivity:({total_bps:number;cost_multiplier:number}&Metric)[]};
export type Event={id:number;type:string;created_at:string;payload:Record<string,unknown>};
export type Edge={id:number;from_experiment_id:string;to_experiment_id:string;relation_type:string;reason_code:string|null;actor_type:string;change_summary:Record<string,unknown>;created_at:string};
export type NodeMetrics={validation:Metric;test:Metric;sharpe_delta:number};
export type Comparison={items:{experiment:Experiment;result:Result}[];differences:{code:string;config:Record<string,unknown>;features_added:string[];features_removed:string[]}[];comparable:boolean;warning:string|null};
export const terminal=(s:string)=>['COMPLETED','FAILED','CANCELLED','TIMEOUT','POLICY_REJECTED'].includes(s);
