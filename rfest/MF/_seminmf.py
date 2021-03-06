import numpy as np
from ._initialize import initialize_factors
from .._splines import build_spline_matrix
from .._utils import softthreshold
__all__ = ['semiNMF']

class semiNMF:

    """
    
    Nonnegative Matrix Factorization with spline-based factors.
    
    Modified from: Ding, et al. (2010)
    
    """

    def __init__(self, V, k=2, init_method='random', random_seed=2046, **kwargs):
        # meta
        self.rcond = kwargs['rcond'] if 'rcond' in kwargs.keys() else None
        self.random_seed = random_seed

        # build basis or not 
        self.build_L = kwargs['build_L'] if 'build_L' in kwargs.keys() else False
        self.build_R = kwargs['build_R'] if 'build_R' in kwargs.keys() else False
        
        self.dims_L = kwargs['dims_L'] if self.build_L else None
        self.df_L = kwargs['df_L'] if self.build_L else None
        
        self.dims_R = kwargs['dims_R'] if self.build_R else None
        self.df_R = kwargs['df_R'] if self.build_R else None
        
        self.smooth_L = kwargs['smooth_L'] if 'smooth_L' in kwargs.keys() else 'cr'
        self.smooth_R = kwargs['smooth_R'] if 'smooth_R' in kwargs.keys() else 'bs'

        self.L = build_spline_matrix(self.dims_L, self.df_L, self.smooth_L) if self.build_L else None
        self.R = build_spline_matrix(self.dims_R, self.df_R, self.smooth_R) if self.build_R else None
        
        # store input data
        self.V = V # data
        
        # data shape / dimension
        self.m, self.n = V.shape
        self.k = k # number of subunits
        self.b = self.L.shape[1] if self.L is not None else None
        self.d = self.R.shape[1] if self.R is not None else None
        
        # initialize W and H

        np.random.seed(random_seed)
    
        # print(f'Initializing semiNMF with `{init_method}`...')
        
        self.W, self.H = initialize_factors(V, k, method=init_method, random_seed=random_seed)

        if self.L is not None:
            if init_method == 'random':
                self.B = np.random.randn(self.b, self.k)
                self.W = self.L @ self.B
            else:
                self.B = np.linalg.lstsq(self.L, self.W, rcond=self.rcond)[0] 
        else:
            self.B = None 
            
        if self.R is not None:    
            if init_method == 'random':
                self.D = np.abs(np.random.randn(self.d, self.k))
                self.H = self.R @ self.D
            else:
                self.D = np.maximum(0, np.linalg.lstsq(self.R, self.H, rcond=self.rcond)[0])
        else:
            self.D = None

        # print('Finished semiNMF initialization.')
    
    def update_W(self):
        
        # data
        V = self.V
        
        # factors 
        H = self.H
        W = self.W
        
        # basis
        L = self.L # basis for left factor
        R = self.R # basis for right factor
        
        # basis coeff
        B = self.B # basis coefficients for left factor
        D = self.D # basis coefficients for right factor

        VH = V @ H
        HtH = H.T @ H
        
        VHHtHinv = VH @ np.linalg.inv(HtH)
        
        if L is not None:
    
            B = np.linalg.lstsq(L, VHHtHinv, rcond=self.rcond)[0]
            W = L @ B
        else:
            
            W = VHHtHinv
        
        if self.build_L:
            W = norm_col(W) 
        
        return W, B
    
    def update_H(self):
        
        def pos(A):
            return (np.abs(A) + A) / 2
        def neg(A):
            return (np.abs(A) - A) / 2
        
        # data
        V = self.V
        
        # factors 
        H = self.H
        W = self.W
        
        # basis
        L = self.L
        R = self.R
        
        # basis coeff
        B = self.B
        D = self.D
        
        VtW = V.T @ W 
        WtW = W.T @ W
        
        if R is not None:
            
            upper = R.T @ pos(VtW) + R.T @ R @ D @ neg(WtW) + 1e-16
            lower = R.T @ neg(VtW) + R.T @ R @ D @ pos(WtW) + 1e-16
            
            D *= np.sqrt(upper / lower)
            H = R @ D
            
        else:
            
            upper = pos(VtW) + H @ neg(WtW) + 1e-16
            lower = neg(VtW) + H @ pos(WtW) + 1e-16
            
            H *= np.sqrt(upper / lower)
        
        if self.build_R:
            H = norm_col(H)

        return H, D

    def compute_cost(self):
        
        V = self.V
        W = self.W
        H = self.H
        WHt = W @ H.T
        
        return np.mean((V - WHt)**2)

    def fit(self, num_iters=300, lambd=0.05, verbal=0, tolerance=10):

        # regularization
        self.lambd= lambd

        if verbal:
            self.cost = []
            self.iter = []
            print('{}\t{}'.format('Iter', 'Cost'))
        
        # start updating
        for itr in range(num_iters):

            self.W, self.B = self.update_W()
            self.H, self.D = self.update_H()

            if verbal:
                if itr % verbal == 0:
                    self.cost.append(self.compute_cost())
                    self.iter.append(itr)
                    print('{}\t{:.3f}'.format(itr, self.cost[-1])) 

                    if len(self.cost) >= 10 and (np.abs(np.diff(self.cost[-10:])) < 1e-7).all():
                        print('Stop: cost has been changing so small in the last {0:03d} chechpoints. Final cost = {1:.3f}'.format(tolerance, self.cost[-1]))
                        break
        else:
            if verbal:
                print('Stop: reached maximum iterations. Final cost = {:.3f}'.format(self.cost[-1]))

def norm_col(X):
    return X / np.linalg.norm(X, axis=0)
