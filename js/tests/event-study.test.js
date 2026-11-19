'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {validate,horizonLabel}=require('../event-study.js');
function sample(){return {schema_version:'event-study-1.0',study_id:'a'.repeat(64),counts:{events:1},
  combined_score:false,trade_assumptions:false,categories:{price_volume:{events:[{
    event_id:'b'.repeat(64),category:'price_volume',rule_id:'price_change',direction:'positive',
    outcomes:[{metric:'close_change_pct',horizon:1,status:'observed',value:'10.000000'}]}],
    summaries:[{group_id:'c'.repeat(64),category:'price_volume',rule_id:'price_change',direction:'positive',
      metric:'close_change_pct',horizon:1,horizon_unit:'quote_observations',events:['b'.repeat(64)],
      n_total:1,n_observed:1,n_unavailable:0,status_counts:{observed:1,pending:0,insufficient_data:0,not_comparable:0},
      statistics:{mean:'10',median:'10',min:'10',max:'10'}}]},monthly_revenue:{events:[],summaries:[]}}};}
test('valid independent descriptive report',()=>assert.equal(validate(sample()).categories.price_volume.events.length,1));
test('no implicit combined score or trading assumptions',()=>{for(const k of ['combined_score','trade_assumptions']){const r=sample();r[k]=true;assert.throws(()=>validate(r));}});
test('schema/version/identity rejected',()=>{for(const [k,v] of [['schema_version','x'],['study_id','../../private']]){const r=sample();r[k]=v;assert.throws(()=>validate(r));}});
test('missing category rejected',()=>{const r=sample();delete r.categories.monthly_revenue;assert.throws(()=>validate(r));});
test('duplicate event and total mismatch rejected',()=>{const r=sample();r.categories.price_volume.events.push(r.categories.price_volume.events[0]);assert.throws(()=>validate(r));r.categories.price_volume.events.pop();r.counts.events=0;assert.throws(()=>validate(r));});
test('missing observations are not zero estimates',()=>{const r=sample(),s=r.categories.price_volume.summaries[0],o=r.categories.price_volume.events[0].outcomes[0];o.status='insufficient_data';o.value=null;s.n_observed=0;s.n_unavailable=1;s.status_counts.observed=0;s.status_counts.insufficient_data=1;s.statistics=null;validate(r);s.statistics={mean:'0',median:'0',min:'0',max:'0'};assert.throws(()=>validate(r));});
test('denominator and status counts checked',()=>{for(const key of ['n_total','n_observed','n_unavailable']){const r=sample();r.categories.price_volume.summaries[0][key]=5;assert.throws(()=>validate(r));}});
test('nonfinite or boolean statistics rejected',()=>{for(const v of ['NaN','Infinity','',true,0]){const r=sample();r.categories.price_volume.summaries[0].statistics.mean=v;assert.throws(()=>validate(r));}});
test('unlisted or duplicate sample ids refused',()=>{const r=sample();r.categories.price_volume.summaries[0].events=['d'.repeat(64)];assert.throws(()=>validate(r));});
test('unknown metric and state rejected',()=>{for(const [k,v] of [['metric','profit'],['status','buy'],['value','NaN']]){const r=sample();r.categories.price_volume.events[0].outcomes[0][k]=v;assert.throws(()=>validate(r));}});
test('unavailable outcome cannot have a value',()=>{const r=sample();r.categories.price_volume.events[0].outcomes[0].status='pending';assert.throws(()=>validate(r));});
test('horizons explicitly say observations not sessions',()=>{assert.equal(horizonLabel({horizon:5,horizon_unit:'quote_observations'}),'後第5筆報價觀察');assert.equal(horizonLabel({horizon:3,horizon_unit:'calendar_months'}),'後3個曆月');});
test('empty report represents zero events without zero means',()=>{const r=sample();r.counts.events=0;r.categories.price_volume={events:[],summaries:[]};validate(r);});
test('excessive event/report dimensions refused',()=>{const r=sample();r.counts.events=2001;assert.throws(()=>validate(r));});
test('analysis version and fact scope visible including old report fallback',()=>{
  const {scopeLabel}=require('../event-study.js');
  assert.match(scopeLabel(sample()),/event-study-1.0.*display_graph_only/);
  const r=sample();r.schema_version='event-study-2.0';r.fact_scope='unpruned_facts';
  r.cohort_selection='explicit';r.counts.included_runs=1;r.counts.runs_after_cutoff=0;r.counts.runs_excluded_by_cohort=1;r.counts.events_excluded_by_origin=0;
  r.inputs=[{run:'1',fact_scope:'unpruned_facts'}];r.excluded_inputs=[{run:'2',fact_scope:'display_graph_only',reason:'different_fact_scope'}];r.excluded_events=[];
  r.cohorts={unpruned_facts:{total_runs:1,included_runs:1,excluded_runs:0},display_graph_only:{total_runs:1,included_runs:0,excluded_runs:1}};
  validate(r);assert.match(scopeLabel(r),/event-study-2.0.*unpruned_facts/);
  r.fact_scope='display_graph_only';assert.throws(()=>validate(r));
});
test('new version cannot omit cohort disclosure or claim mixed denominator',()=>{
  const r=sample();r.schema_version='event-study-2.0';assert.throws(()=>validate(r));
  r.fact_scope='unpruned_facts';assert.throws(()=>validate(r));
  r.schema_version='event-study-1.0';assert.throws(()=>validate(r));
});
test('versioned cohort reader checks both directions of event membership and exclusion reasons',()=>{
  const r=sample(), group=r.categories.price_volume.summaries[0], event=r.categories.price_volume.events[0];
  const row=event.outcomes[0], settings='d'.repeat(64);
  r.cohort_policy={version:'event-cohorts-1',settings_id:settings};
  Object.assign(event,{settings_id:settings,event_at:'2020-08-15T12:00:00Z',repeat_runs:[],repeated_captures:0});
  Object.assign(row,{group_id:group.group_id,reason:'target_calendar_month_not_ended',status:'pending',value:null,
    followup_window:{start_at:event.event_at,end_at:'2020-08-16T12:00:00Z',right_censored:true,same_stock_overlapping_events:0}});
  Object.assign(group,{settings_id:settings,n_right_censored:1,n_observed:0,n_unavailable:1,statistics:null,
    status_counts:{observed:0,pending:1,insufficient_data:0,not_comparable:0},unavailable_by_reason:{[row.reason]:[event.event_id]}});
  r.fact_scope='display_graph_only';r.cohort_selection='explicit';
  const run='1'.repeat(32), digest='a'.repeat(64), other='2'.repeat(32), excluded='e'.repeat(64);
  const repeat='3'.repeat(32), stamp=event.event_at;
  r.inputs=[run,repeat].map(run=>({run,report_sha256:digest,completed_at:stamp,fact_scope:r.fact_scope}));
  r.excluded_inputs=[{run:other,report_sha256:digest,completed_at:stamp,
    fact_scope:'unpruned_facts',reason:'different_fact_scope'}];
  Object.assign(r.counts,{included_runs:2,runs_after_cutoff:0,runs_excluded_by_cohort:1,
    events_excluded_by_origin:1,duplicate_period_events_suppressed:1});
  r.cohorts={display_graph_only:{total_runs:2,included_runs:2,excluded_runs:0},
    unpruned_facts:{total_runs:1,included_runs:0,excluded_runs:1}};
  r.excluded_events=[{event_id:excluded,category:'monthly_revenue',rule_id:'revenue_yoy',first_run:other,
    first_event_at:stamp,first_fact_scope:'unpruned_facts',first_report_sha256:digest,
    reason:'first_trigger_saved_in_other_cohort',selected_runs:[run]}];
  r.categories.monthly_revenue.excluded_by_origin=[excluded];r.categories.price_volume.excluded_by_origin=[];
  Object.assign(event,{run,report_sha256:digest,definition_id:digest,repeat_runs:[repeat],repeated_captures:1});
  Object.assign(row,{horizon_unit:'quote_observations',unit:'percent',basis:{source_id:'fixture'}});
  Object.assign(group,{definition_id:digest,unit:row.unit,basis:{...row.basis}});
  validate(r);
  const mutations=[
    v=>{v.categories.price_volume.summaries[0].rule_id='revenue_yoy';},
    v=>{v.categories.price_volume.summaries[0].definition_id='b'.repeat(64);},
    v=>{v.categories.price_volume.summaries[0].basis.source_id='other';},
    v=>{v.categories.price_volume.summaries[0].unit='ratio';},
    v=>{v.categories.price_volume.events[0].repeat_runs[0]='9'.repeat(32);},
    v=>{v.categories.monthly_revenue.excluded_by_origin[0]='9'.repeat(64);},
    v=>{v.excluded_events[0].selected_runs=['9'.repeat(32)];},
  ];
  for (const mutate of mutations) {
    const altered=structuredClone(r); mutate(altered); assert.throws(()=>validate(altered),undefined,String(mutate));
  }
  row.group_id='a'.repeat(64);assert.throws(()=>validate(r));row.group_id=group.group_id;
  group.unavailable_by_reason={};assert.throws(()=>validate(r));group.unavailable_by_reason={[row.reason]:[event.event_id]};
  group.n_right_censored=0;assert.throws(()=>validate(r));group.n_right_censored=1;
  r.cohort_policy.version='unknown';assert.throws(()=>validate(r));
});
