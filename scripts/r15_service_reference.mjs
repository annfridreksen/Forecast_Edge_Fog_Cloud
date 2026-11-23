// R1.5 A6. Run with node scripts/r15_service_reference.mjs; no simulation.
function calculate(){
 const fixed=[[5,15],[30,80],[20,50],[10,30]], mobile=[[8,20],[30,80],[20,50],[10,30]];
 function cdf(x, ranges){
   const n=ranges.length, a=ranges.reduce((s,r)=>s+r[0],0), w=ranges.map(r=>r[1]-r[0]), sum=w.reduce((s,v)=>s+v,0);
   if(x<=a)return 0; if(x>=a+sum)return 1;
   // Reflect around the midpoint to avoid cancellation near upper support.
   if(x>a+sum/2)return 1-cdf(2*a+sum-x,ranges);
   let numerator=0;
   for(let mask=0;mask<(1<<n);mask++){
     let d=x-a, sign=1;
     for(let j=0;j<n;j++)if(mask&(1<<j)){d-=w[j];sign=-sign;}
     numerator+=sign*Math.max(d,0)**n;
   }
   let denominator=1;for(let j=0;j<n;j++)denominator*=(j+1)*w[j];
   return numerator/denominator;
 }
 const mix=x=>0.7*cdf(x,fixed)+0.3*cdf(x,mobile);
 function quantile(f,p){let lo=65,hi=180;for(let i=0;i<70;i++){const mid=(lo+hi)/2;if(f(mid)<p)lo=mid;else hi=mid;}return (lo+hi)/2;}
 const q=quantile(mix,.95);
 function assert(ok,msg){if(!ok)throw Error(msg);}
 let tests=[];
 assert(cdf(65,fixed)===0&&cdf(175,fixed)===1&&cdf(68,mobile)===0&&cdf(180,mobile)===1,"support");tests.push("both support endpoints");
 assert(Math.abs(cdf(0.25,[[0,1]])-.25)<1e-12&&Math.abs(cdf(.5,[[0,1],[0,1]])-.125)<1e-12,"known CDF");tests.push("one uniform and triangular oracle");
 assert(Math.abs(cdf(120,fixed)-.5)<1e-12&&Math.abs(cdf(124,mobile)-.5)<1e-12,"symmetry");tests.push("conditional midpoint symmetry");
 let prev=0;for(let x=65;x<=180;x+=.1){const v=mix(x);assert(v>=prev-1e-12&&v>=-1e-12&&v<=1+1e-12,"monotonicity");prev=v;}tests.push("mixture monotonicity and range");
 assert(Math.abs(mix(q)-.95)<1e-12&&mix(q-.0001)<.95&&mix(q+.0001)>.95,"quantile");tests.push("quantile bracket and CDF residual");
 assert(mix(200)===1,"threshold");tests.push("service support below deadline");
 return {schema:"FEFC-R15-service-reference-1",distribution:"continuous model-law marginal over random sensor labels, not an empirical or conditional-on-completion quantile",source_blobs:{"efc/model.py":"28539aa3173544d003b58231388ffadb18b63efc","efc/workload.py":"3497c507ae6e47f94df46703ef1507983fd26744","efc/timebase.py":"5e990f9dd058bc5f2290f2fdcebde8f4ae9c1ccf"},weights:{fixed:.7,mobile:.3},uniform_ranges_ms:{fixed,mobile},mean_ms:121.2,p95_ms:{fixed:quantile(x=>cdf(x,fixed),.95),mobile:quantile(x=>cdf(x,mobile),.95),mixture:q},cdf_at_mixture_p95:mix(q),max_service_ms:180,service_cdf_at_200ms:mix(200),rounding_bound_ms:0.000002,tests,interpretation:"Model-law marginal uses independent uniform primitive draws conditional on sensor type; Edge and EF are split from one draw, not independent. Sensor types fixed within a replication, realized mobile share may differ from 0.30. Sum excludes all waiting. Four primitive durations rounded to nearest ns; split conserves ticks. No claim of lower bound on p95 conditional on completion, no grid pruning, no new simulation/bootstrap."};
}
console.log(JSON.stringify(calculate(),null,2));
