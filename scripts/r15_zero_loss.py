"""Separate R1.5 analysis approved in Issue #5/7115069628 and 7115236266.
Uses real main arrivals per seed. No simulation, bootstrap or R1.4 mutation.
Independence/common Bernoulli risk is an explicit assumption, not inferred.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, math, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from efc.grid import digest, read_json
KEY='r0.10_F30_B005'


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def upper(n):
    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<=0:
        raise ValueError('positive effective arrival count required')
    return -math.expm1(math.log(.025)/n)


def decide(rows,q,pilot_ready,other_reasons):
    if len(rows)!=10 or sorted(r['seed'] for r in rows)!=list(range(10)):
        raise ValueError('exactly one main replication per seed 0..9 required')
    for r in rows:
        if type(r['arrivals']) is not int or r['arrivals']<=0 or r['arrivals']!=r['completed']+r['dropped']+r['unfinished']:
            raise ValueError('invalid main cohort balance')
    if any(r['dropped'] for r in rows):raise ValueError('nonzero losses require the unchanged whole-replication bootstrap')
    if any(r['unfinished'] for r in rows):raise ValueError('unfinished replications cannot establish acceptance')
    n=min(r['arrivals'] for r in rows);u=upper(n)
    prerequisites=bool(pilot_ready and not other_reasons)
    precision=q['half_width']<=10 and u/2<=.00005
    limits=q['upper']<=200 and u<=.001
    return {'n_min':n,'U_L':u,'U_Q_ms':q['upper'],'loss_interval':[0.0,u],
            'prerequisites_ok':prerequisites,'precision_ok':precision,'joint_thresholds_ok':limits,
            'status':'CONDITIONALLY_ACCEPTABLE' if prerequisites and precision and limits else 'INSUFFICIENT_DATA',
            'interpretation':'допустима при указанном допущении' if prerequisites and precision and limits else 'недостаточно данных',
            'assumption':'Independent Bernoulli message-loss outcomes with a common probability; dependence of the actual queue has not been established or removed.'}


def analysis(root):
    root=Path(root);main_path=root/'cells'/KEY/'main.json'
    main=read_json(main_path);pilot=read_json(root/'cells'/KEY/'pilot.json')
    mapping=read_json(root/'map.json');manifest=read_json(root/'manifest.json')
    row=next(r for r in mapping['rows'] if r['key']==KEY)
    if (mapping['manifest_sha256']!=digest(manifest) or row['main_sha256']!=digest(main)
        or main['summary']!=row['summary'] or digest(pilot['plan'])!=pilot['plan_sha256']
        or main['plan_sha256']!=pilot['plan_sha256'] or main['config_id']!=pilot['config_id']):
        raise ValueError('broken frozen evidence chain')
    rows=[]
    for r in main['runs']:
        req={k:r[k] for k in ('seed','warmup','observe','guard')};req['config_id']=main['config_id']
        path=root/'observations'/main['config_id']/(digest(req)+'.json.gz')
        obj=json.loads(gzip.decompress(path.read_bytes()));o=obj['observation'];full=o['full']
        if obj['request']!=req or obj['sha256']!=digest(o) or full['seed']!=req['seed']:
            raise ValueError('primary identity/hash mismatch')
        rows.append(dict(seed=req['seed'],arrivals=full['arrivals'],completed=len(full['latency_ticks']),
                         dropped=full['dropped'],unfinished=full['unfinished'],request=req,
                         path=str(path.relative_to(root)),sha256=sha(path)))
    rows.sort(key=lambda r:r['seed'])
    reasons=[r for r in main['summary']['reasons'] if r!='zero_loss_degenerate_bootstrap']
    decision=decide(rows,main['summary']['intervals']['p95_ms'],pilot['status']=='READY',reasons)
    sens=[]
    for factor in (1,5,10,50,100):
        neff=decision['n_min']/factor;u=upper(neff)
        sens.append(dict(reduction_factor=factor,n_eff=neff,U_L=u,loss_threshold_pass=u<=.001,
                         old_precision_pass=u/2<=.00005,interpretation='assumed effective-volume scenario, not measured dependence'))
    lam=50*.1/.055;mu=1/.055;F=30;B=5;K=B+1
    groups=[];approx=0.
    for m,count in ((33,20),(34,10)):
        arrival=lam*m/1000;rho=arrival/mu;p=rho**K/sum(rho**j for j in range(K+1));weight=count*m/1000
        groups.append(dict(sensors_per_node=m,nodes=count,lambda_per_s=arrival,rho=rho,blocking=p,arrival_weight=weight));approx+=weight*p
    return dict(schema='R1.5-author69-conditional-analysis-1',key=KEY,
      author_decisions=[7115069628,7115236266],source_run_id=45174257711,
      source_zip_sha256='2cb91dbc964a641c36fb53e02ddea3590bf8fe939933f43b31399267508d40ef',
      main_sha256=sha(main_path),manifest_sha256=digest(manifest),config_id=main['config_id'],
      analysis_code_sha256=sha(__file__),rows=rows,decision=decision,
      previous_R14_status=main['status'],previous_R14_reasons=main['summary']['reasons'],
      removed_reason_for_conditional_analysis_only='zero_loss_degenerate_bootstrap',
      other_reasons=reasons,pilot_ready=pilot['status']=='READY',sensitivity=sens,
      sufficient_threshold_n=3689,U_at_3689=upper(3689),
      max_reduction_for_sufficient_threshold=decision['n_min']/3689,
      precision_required_n=math.ceil(math.log(.025)/math.log1p(-.0001)),
      mm1k=dict(lambda_total=lam,mu=mu,F=F,B=B,K=K,groups=groups,arrival_weighted_loss=approx,
               interpretation='Approximation for Poisson arrivals directly to separate Fog queues and exponential service, unlike the full FEFC model; not a bound.'),
      raw_data_mutated=False,simulation_executed=False,bootstrap_recomputed=False,
      independent_confirmation=False,minimum_configuration_established=False)


def macros(obj):
    d=obj['decision'];rows=obj['rows'];u=d['U_L']*100
    vals={'cNmin':str(d['n_min']),'cLossPercent':f'{u:.5f}'.replace('.',','),
          'cLossPercentEN':f'{u:.5f}','cFiftyBound':f"{upper(d['n_min']/50)*100:.4f}".replace('.',','),
          'cReduction':f"{obj['max_reduction_for_sufficient_threshold']:.1f}".replace('.',','),
          'cQueuePercent':f"{obj['mm1k']['arrival_weighted_loss']*100:.5f}".replace('.',','),
          'cCounts':', '.join(str(r['arrivals']) for r in rows)}
    return '% Separate conditional analysis; raw R1.4 output remains unchanged.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in vals.items())


class RuleTests(unittest.TestCase):
    def fixture(self):return [dict(seed=i,arrivals=200000-i,completed=200000-i,dropped=0,unfinished=0) for i in range(10)]
    def decide(self,rows,**kw):return decide(rows,kw.get('q',dict(upper=171.,half_width=.2)),kw.get('pilot',True),kw.get('reasons',[]))
    def test_min_not_sum(self):self.assertEqual(self.decide(self.fixture())['n_min'],199991)
    def test_not_aggregate(self):self.assertNotEqual(self.decide(self.fixture())['U_L'],upper(sum(r['arrivals'] for r in self.fixture())))
    def test_zero_rule_formula(self):self.assertAlmostEqual(upper(3689),1-.025**(1/3689),places=15)
    def test_sufficient_threshold(self):self.assertLessEqual(upper(3689),.001)
    def test_precision_is_distinct(self):self.assertGreater(upper(4000)/2,.00005);self.assertLess(upper(4000),.001)
    def test_fifty_scenario_not_full_acceptance(self):self.assertFalse(upper(200000/50)/2<=.00005)
    def test_nonzero_rejected(self):
        r=self.fixture();r[0].update(dropped=1,completed=199999)
        with self.assertRaises(ValueError):self.decide(r)
    def test_pending_rejected(self):
        r=self.fixture();r[0].update(unfinished=1,completed=199999)
        with self.assertRaises(ValueError):self.decide(r)
    def test_duplicate_rejected(self):
        r=self.fixture();r[-1]['seed']=0
        with self.assertRaises(ValueError):self.decide(r)
    def test_pilot_not_ready(self):self.assertEqual(self.decide(self.fixture(),pilot=False)['status'],'INSUFFICIENT_DATA')
    def test_other_reason_preserved(self):self.assertEqual(self.decide(self.fixture(),reasons=['bad'])['status'],'INSUFFICIENT_DATA')
    def test_q_limit_preserved(self):self.assertEqual(self.decide(self.fixture(),q=dict(upper=201,half_width=.2))['status'],'INSUFFICIENT_DATA')
    def test_q_precision_preserved(self):self.assertEqual(self.decide(self.fixture(),q=dict(upper=171,half_width=11))['status'],'INSUFFICIENT_DATA')
    def test_conditional_not_unconditional(self):self.assertEqual(self.decide(self.fixture())['status'],'CONDITIONALLY_ACCEPTABLE')
    def test_invalid_n(self):
        for n in (0,-1,True,float('nan')):
            with self.assertRaises(ValueError):upper(n)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/'zero-loss-tests.log').open('w') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuleTests))
    if not result.wasSuccessful():raise SystemExit(1)
    obj=analysis(a.checkpoint);obj['tests_passed']=result.testsRun
    (a.out/'conditional-analysis.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    (a.out/'conditional-values.tex').write_text(macros(obj))
    print(json.dumps(obj,ensure_ascii=False))
