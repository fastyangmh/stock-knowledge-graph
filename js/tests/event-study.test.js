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
