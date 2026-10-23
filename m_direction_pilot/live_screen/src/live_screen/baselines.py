"""Shared fixed-frame PSD rank summaries. No teacher, policy training or Hessian estimate."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .io import config
from m_direction.perturb import DIRECTIONS

MODELS=['scalar','world_diag','world_full_PSD3x3','object_diag','object_full_PSD3x3','task_full_PSD3x3','contact_full_PSD3x3_if_reliable']


def matrix(p,diagonal=False):
    return np.diag(p) if diagonal else np.array([[p[0],p[3],p[4]],[p[3],p[1],p[5]],[p[4],p[5],p[2]]])


def features(d,diagonal=False):
    x,y,z=d
    return np.array([x*x,y*y,z*z]) if diagonal else np.array([x*x,y*y,z*z,2*x*y,2*x*z,2*y*z])


def eigen_jacobian(p,diagonal=False):
    """Analytic eigenvalue derivatives in the frozen symmetric coordinates."""
    _,vectors=np.linalg.eigh(matrix(p,diagonal))
    return np.stack([features(v,diagonal) for v in vectors.T])


def frame(model,r):
    if model.startswith('world') or model=='scalar':return np.eye(3)
    if model.startswith('object'):return r['geometry']['object_rotation']
    if model.startswith('task'):return r['geometry']['task_rotation']
    return r['geometry']['contact_rotation']


def model_pairs(model,records,split):
    diagonal=model.endswith('diag');pairs=[];valid_states=[]
    for sid in sorted({r['state_id'] for r in records if r['split']==split and r['stage']!='A'}):
        rr=[r for r in records if r['state_id']==sid and r['stage']!='A' and r['direction']!='nominal' and r['status']=='completed']
        if not rr:continue
        R=frame(model,rr[0])
        if R is None:continue
        R=np.asarray(R);np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-10,rtol=0)
        fail=[r for r in rr if not r['ever_success']];safe=[r for r in rr if r['ever_success']]
        if not fail or not safe:continue
        valid_states.append((sid,rr[0]['source_episode']))
        for a in fail:
            for b in safe:
                da=R.T@(DIRECTIONS[a['direction']]*a['sign']);db=R.T@(DIRECTIONS[b['direction']]*b['sign'])
                pairs.append({'state_id':sid,'source_episode':a['source_episode'],'failed_branch':a['branch_id'],'safe_branch':b['branch_id'],
                              'x':features(da,diagonal)-features(db,diagonal)})
    return pairs,valid_states


def evaluate(model,M,records,split):
    pairs,states=model_pairs(model,records,split)
    diagonal=model.endswith('diag')
    p=np.diag(M) if diagonal else np.array([M[0][0],M[1][1],M[2][2],M[0][1],M[0][2],M[1][2]])
    rows=[];tol=config()['rank_margin_tolerance']
    for row in pairs:
        margin=float(row['x']@p)
        rows.append({k:v for k,v in row.items() if k!='x'}|{'margin':margin,'ranking':'correct' if margin>tol else 'violation' if margin < -tol else 'tie'})
    by_state=[]
    for sid,episode in states:
        subset=[r for r in rows if r['state_id']==sid]
        by_state.append({'state_id':sid,'source_episode':episode,'pairs':len(subset),
            **{k:sum(r['ranking']==k for r in subset) for k in ['correct','violation','tie']}})
    return {'available_informative_states':states,'by_state':by_state,'raw_pairs':rows,
            'informative_episodes':sorted({e for _,e in states}),
            'all_comparable_ranks_correct':bool(rows) and all(r['ranking']=='correct' for r in rows)}


def fit_all(records):
    cfg=config();output={}
    dev=[r for r in records if r['split']=='development' and r['stage']!='A']
    assert not any(r['stage']=='B3' for r in dev)
    for model in MODELS:
        if model=='scalar':
            output[model]={'available':True,'matrix':np.eye(3),'fit':'no fitted parameters, same norm ties',
                           'dev_ranks':evaluate(model,np.eye(3),dev,'development')};continue
        pairs,states=model_pairs(model,dev,'development')
        episodes=sorted({ep for _,ep in states})
        if len(episodes)<2 or not pairs:
            output[model]={'available':False,'reason':'fewer than two dev episodes with reliable geometry and informative ranks'};continue
        diagonal=model.endswith('diag');X=np.stack([r['x'] for r in pairs])
        weights=[]
        for r in pairs:
            ns=sum(ep==r['source_episode'] for _,ep in states)
            npairs=sum(x['state_id']==r['state_id'] for x in pairs)
            weights.append(1/(len(episodes)*ns*npairs))
        w=np.array(weights);assert abs(w.sum()-1)<1e-10
        init=np.ones(3) if diagonal else np.array([1.,1.,1.,0.,0.,0.])
        multiplicity=np.ones(3) if diagonal else np.array([1,1,1,2,2,2])
        def objective(p):
            score=X@p;dist=p-init
            return float(w@np.logaddexp(0.,-score)+cfg['ranking_regularization']*np.sum(multiplicity*dist*dist))
        def jac(p):
            return -X.T@(w*expit(-(X@p)))+2*cfg['ranking_regularization']*multiplicity*(p-init)
        constraints=[{'type':'eq','fun':lambda p:np.sum(p[:3])-3.,
                      'jac':lambda p:np.r_[np.ones(3),np.zeros(len(p)-3)]},
                     {'type':'ineq','fun':lambda p:np.linalg.eigvalsh(matrix(p,diagonal)),
                      'jac':lambda p:eigen_jacobian(p,diagonal)}]
        opt=minimize(objective,init,jac=jac,method='SLSQP',constraints=constraints,
                     bounds=[(0.,3.)]*3+([] if diagonal else [(-3.,3.)]*3),
                     options={'maxiter':cfg['optimizer']['maxiter'],'ftol':cfg['optimizer']['ftol']})
        M=matrix(opt.x,diagonal)
        valid=bool(opt.success) and np.linalg.eigvalsh(M).min()>=-1e-7 and abs(np.trace(M)-3)<1e-7
        output[model]={'available':valid,'matrix':M if valid else None,'optimizer_success':bool(opt.success),
                       'optimizer_message':str(opt.message),'objective':float(opt.fun),'iterations':int(opt.nit),
                       'scope':'dev-only shared fixed-frame exploratory binary ranking, not probability/Q/Hessian',
                       'dev_ranks':evaluate(model,M,dev,'development') if valid else None}
    return output
