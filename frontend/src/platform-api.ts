export const token=()=>sessionStorage.getItem('regimelab-token')||'';
export const lang=()=>{try{const v=localStorage.getItem('regimelab.lang');return v==='en'?'en':'tr';}catch{return 'tr';}};
export const headers=()=>({'Content-Type':'application/json','X-RegimeLab-Source':'WEB','Accept-Language':lang(),...(token()?{Authorization:`Bearer ${token()}`}:{})});
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
export type Spec={schema_version:'1.0';name:string;description:string;tags:string[];market:'FX';symbol:'EURUSD';dataset_id:string;timeframe:string;features:{groups:string[];families:string[];names:string[]};models:string[];optimization:{algorithm:string;population:number;generations:number;mutation_rate:number;crossover_rate:number;elitism:number;min_features:number;max_features:number;hyperparameters:boolean;objective:string;max_drawdown:number;thresholds_bps?:number[]};validation:{method:string;train_ratio:number;folds:number;gap:number;locked_test:true};backtest:{capital:number;cost_bps:number;slippage_bps:number};seed:number;regime_states:number;search_space_id?:string|null};
export const defaultSpec:Spec={schema_version:'1.0',name:'EURUSD araştırması',description:'',tags:[],market:'FX',symbol:'EURUSD',dataset_id:'demo',timeframe:'native',features:{groups:['technical'],families:[],names:[]},models:['ridge','xgboost'],optimization:{algorithm:'genetic',population:8,generations:4,mutation_rate:.12,crossover_rate:.8,elitism:2,min_features:3,max_features:30,hyperparameters:true,objective:'sharpe',max_drawdown:.5},validation:{method:'walk_forward',train_ratio:.65,folds:3,gap:2,locked_test:true},backtest:{capital:10000,cost_bps:.5,slippage_bps:.2},seed:42,regime_states:3};
export type Metric={sharpe:number;return:number;max_drawdown:number;sortino:number;position_changes:number;win_rate:number;turnover:number};
export type Experiment={id:string;code:string;name:string;parent_id:string|null;status:string;created_at:string;specification:Spec;snapshot:{id:string;sha256:string;details:{name:string;rows:number;demo:boolean;start:string;end:string;point_in_time:string;[key:string]:unknown}};run:null|{id:string;status:string;progress:number;message:string;metrics:Metric|null;duration_seconds:number|null}};
export type Curve={timestamp:string;equity:number;benchmark:number;drawdown:number;return:number;signal:number;prediction_bps:number};
export type Candidate={id:string;model:string;features:string[];parameters:Record<string,number>;metrics:Metric;fitness:number;feasible:boolean;threshold_bps:number;folds:({train_end:string;validation_start:string;validation_end:string;gap_bars:number}&Metric)[]};
export type Generation={generation:number;total_generations:number;best_fitness:number;mean_fitness:number;diversity:number;candidate_count:number;best:Candidate};
export type Optimization={best:Candidate;candidates:Candidate[];generations:Generation[];pareto:Candidate[];survival:{feature:string;selection_frequency:number;top_survival:number;fitness_present:number|null;fitness_absent:number|null}[]};
export type Result={metrics:Metric;validation_metrics:Metric;validation_test_sharpe_delta:number;curve:Curve[];selected_model:string;selected_features:string[];parameters:Record<string,number>;optimization:Optimization;warnings:string[];split:{development:number;test:number;gap:number;test_start:string;test_end:string};feature_analysis:{features:{feature:string;ic:number;rolling_ic:number[];sign_consistency:number;mutual_information:number}[];redundancy_pairs:{a:string;b:string;correlation:number}[]};regimes:{id:number;bars:number;share:number;mean_net_return_bps:number|null}[];cost_sensitivity:({total_bps:number;cost_multiplier:number}&Metric)[]};
export type Event={id:number;type:string;created_at:string;payload:Record<string,unknown>};
export type Comparison={items:{experiment:Experiment;result:Result}[];differences:{code:string;config:Record<string,unknown>;features_added:string[];features_removed:string[]}[];comparable:boolean;warning:string|null};
export type PlatformModel={id:string;name:string;status?:string};
export const terminal=(s:string)=>['COMPLETED','FAILED','CANCELLED','TIMEOUT','POLICY_REJECTED'].includes(s);
