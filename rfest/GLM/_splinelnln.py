import jax.numpy as np
import jax.random as random
from jax import grad
from jax import jit
from jax.experimental import optimizers

from jax.config import config
config.update("jax_enable_x64", True)

from ._base import splineBase
from .._splines import build_spline_matrix

__all__ = ['splineLNLN']

class splineLNLN(splineBase):

    def __init__(self, X, y, dims, df, smooth='cr', compute_mle=True, **kwargs):
        
        super().__init__(X, y, dims, df, smooth, compute_mle, **kwargs)

    def cost(self, b):

        """

        Negetive Log Likelihood.

        """
        
        XS = self.XS
        y = self.y
        dt = self.dt
        
        def nonlin(x):
            return np.log(1 + np.exp(x)) + 1e-17

        
        if self.n_subunits == 1:
            filter_output = nonlin(XS @ b).flatten()
            r = dt * filter_output
        else:
            filter_output = np.sum(nonlin(XS @ b.reshape(self.n_b, self.n_subunits)), 1)
            r = dt * nonlin(filter_output).flatten() # conditional intensity (per bin)
        
        term0 = - np.log(r) @ y # spike term from poisson log-likelihood
        term1 = np.sum(r) # non-spike term

        neglogli = term0 + term1
        
        if self.lambd:
            l1 = np.sum(np.abs(b))
            l2 = np.sqrt(np.sum(b**2)) 
            neglogli += self.lambd * ((1 - self.alpha) * l2 + self.alpha * l1)
        # nuc = np.linalg.norm(b.reshape(self.n_b, self.n_subunits), 'nuc') # wait for JAX update
        if self.gamma:
            nuc = np.sum(np.linalg.svd(b.reshape(self.n_b, self.n_subunits), full_matrices=False, compute_uv=False), axis=-1)
            neglogli += self.gamma * nuc
        
        return neglogli

    def fit(self, p0=None, num_subunits=1, num_iters=5, alpha=0.5, lambd=0.05, gamma=0.0,
            step_size=1e-2, tolerance=10, verbal=1, random_seed=2046):

        self.lambd = lambd # elastic net parameter - global weight
        self.alpha = alpha # elastic net parameter (1=L1, 0=L2)
        self.gamma = gamma # nuclear norm parameter
        
        self.n_subunits = num_subunits
        self.num_iters = num_iters   
        
        if p0 is None:
        
            key = random.PRNGKey(random_seed)
            p0 = 0.01 * random.normal(key, shape=(self.n_b, self.n_subunits)).flatten()
        
        self.b_opt = self.optimize_params(p0, num_iters, step_size, tolerance, verbal)   
        self.w_opt = self.S @ self.b_opt.reshape(self.n_b, self.n_subunits)


# class splineLNLN:

#     """
    
#     Spline-based multi-filters Linear-Nonliear-Poisson model with fixed (softplus) nonlinearity. 
    
#     """
    
#     def __init__(self, X, y, dt, dims, df, smooth='cr', compute_mle=True):
        
#         self.X = np.array(X) # stimulus design matrix
#         self.y = np.array(y) # response 
#         self.dt = dt # time bin size 
        
#         self.dims = dims # assumed order [t, y, x]
#         self.ndim = len(dims)
#         self.n_samples, self.n_features = X.shape

#         if compute_mle:
#             self.w_mle = np.linalg.solve(X.T @ X, X.T @ y)
#         else:
#             self.w_mle = None
        
#         S = np.array(build_spline_matrix(dims, df, smooth))
#         self.S = S
#         self.XS = X @ S
#         self.n_spline_coeff = self.S.shape[1]
#         self.b_spl = np.linalg.solve(self.XS.T @ self.XS, S.T @ X.T @ y)
#         self.w_spl = S @ self.b_spl
       
#     def cost(self, B):

#         """

#         Negetive log likelihood cost function.

#         """
        
#         XS = self.XS
#         y = self.y
#         dt = self.dt
        
#         def nonlin(x):
#             return np.log(1 + np.exp(x)) + 1e-17

#         filter_output = np.sum(nonlin(XS @ B.reshape(self.n_spline_coeff, self.n_subunits)), 1)
        
#         r = dt * nonlin(filter_output).flatten() # conditional intensity (per bin)
#         term0 = - np.log(r) @ y # spike term from poisson log-likelihood
#         term1 = np.sum(r) # non-spike term

#         neglogli = term0 + term1
        
#         if self.lambd:
#             l1 = np.linalg.norm(B, 1)
#             l2 = np.linalg.norm(B, 2)
#             neglogli += self.lambd * ((1 - self.alpha) * l2 + self.alpha * l1)
#         # nuc = np.linalg.norm(B.reshape(self.n_spline_coeff, self.n_subunits), 'nuc') # wait for JAX update
#         if self.gamma:
#             nuc = np.sum(np.linalg.svd(B.reshape(self.n_spline_coeff, self.n_subunits), full_matrices=False, compute_uv=False), axis=-1)
#             neglogli += self.gamma * nuc
        
#         return neglogli
        
#     def optimize_params(self, p0, num_iters, step_size, tolerance, verbal):
        
#         opt_init, opt_update, get_params = optimizers.adam(step_size=step_size)
#         opt_state = opt_init(p0)
        
#         @jit
#         def step(i, opt_state):
#             p = get_params(opt_state)
#             g = grad(self.cost)(p)
#             return opt_update(i, g, opt_state)

#         cost_list = []
#         params_list = []    

#         if verbal:
#             print('{0}\t{1}\t'.format('Iter', 'Cost'))

#         for i in range(num_iters):
            
#             opt_state = step(i, opt_state)
#             params_list.append(get_params(opt_state))
#             cost_list.append(self.cost(params_list[-1]))
            
#             if verbal:
#                 if i % int(verbal) == 0:
#                     print('{0}\t{1:.3f}\t'.format(i,  cost_list[-1]))
            
#             if len(params_list) > tolerance:
                
#                 if np.all((np.array(cost_list[1:])) - np.array(cost_list[:-1]) > 0 ):
#                     params = params_list[0]
#                     if verbal:
#                         print('Stop at {} steps: cost has been monotonically increasing for {} steps.'.format(i, tolerance))
#                     break
#                 elif np.all(np.array(cost_list[:-1]) - np.array(cost_list[1:]) < 1e-5):
#                     params = params_list[-1]
#                     if verbal:
#                         print('Stop at {} steps: cost has been changing less than 1e-5 for {} steps.'.format(i, tolerance))
#                     break                    
#                 else:
#                     params_list.pop(0)
#                     cost_list.pop(0)     
#         else:
#             params = params_list[-1]
#             if verbal:
#                 print('Stop: reached {} steps, final cost={}.'.format(num_iters, cost_list[-1]))
            
            
#         return params      
    
#     def fit(self, p0=None, num_subunits=1, num_iters=5, alpha=0.5, lambd=0.05, gamma=0.0,
#             step_size=1e-2, tolerance=10, verbal=True, random_seed=2046):

#         self.lambd = lambd # elastic net parameter - global weight
#         self.alpha = alpha # elastic net parameter (1=L1, 0=L2)
#         self.gamma = gamma # nuclear norm parameter
        
#         self.n_subunits = num_subunits
#         self.num_iters = num_iters   
        
#         if p0 is None:
        
#             key = random.PRNGKey(random_seed)
#             p0 = 0.01 * random.normal(key, shape=(self.n_spline_coeff, self.n_subunits)).flatten()
        
#         self.B_opt = self.optimize_params(p0, num_iters, step_size, tolerance, verbal)   
#         self.w_opt = self.S @ self.B_opt.reshape(self.n_spline_coeff, self.n_subunits)
