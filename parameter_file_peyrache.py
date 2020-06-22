from scipy import *
import scipy.io
import scipy.ndimage
import numpy as np
import scipy.optimize as spoptim
import numpy.random
import matplotlib
#matplotlib.use('Agg') # When running on cluster, plots cannot be shown and this must be used
import matplotlib.pyplot as plt
import time
import sys
plt.rc('image', cmap='viridis')
from scipy import optimize
numpy.random.seed(13)
from multiprocessing import Pool
from sklearn.decomposition import PCA

################################################
# Parameters for inference, not for generating #
################################################
T = 2000 #2000 # Max time 85504
N = 16 
print("N =", N, "but take care that it must be changed manually if neuron screening settings are changed")
N_iterations = 20
global_initial_sigma_n = 2.5
sigma_n = np.copy(global_initial_sigma_n) # Assumed variance of observations for the GP that is fitted. 10e-5
lr = 0.99 # Learning rate by which we multiply sigma_n at every iteration

# Parameters for data loading    #
downsampling_factor = 2 #supreme: 2
offset = 70400 #64460 (not so good) #68170 (getting stuck lower in middle) # 70400 (supreme)

KEEP_PATH_BETWEEN_ZERO_AND_TWO_PI = False
INFER_F_POSTERIORS = True
GRADIENT_FLAG = True # Set True to use analytic gradient
USE_OFFSET_AND_SCALING_AT_EVERY_ITERATION = False
USE_OFFSET_AND_SCALING_AFTER_CONVERGENCE = True
TOLERANCE = 1e-5
X_initialization = "flatrandom" #"true" "ones" "pca" "randomrandom" "flatrandom" "randomprior" "linspace" "supreme"
smoothingwindow_for_PCA = 20
PCA_TYPE = "angle" #"angle" "1d"
LET_INDUCING_POINTS_CHANGE_PLACE_WITH_X_ESTIMATE = False # If False, they stay at (min_inducing_point, max_inducing_point)
FLIP_AFTER_SOME_ITERATION = False
FLIP_AFTER_HOW_MANY = 1
NOISE_REGULARIZATION = False
SMOOTHING_REGULARIZATION = False
GIVEN_TRUE_F = False
SPEEDCHECK = False
OPTIMIZE_HYPERPARAMETERS = False
PLOTTING = True
LIKELIHOOD_MODEL = "poisson" # "bernoulli" "poisson"
COVARIANCE_KERNEL_KX = "nonperiodic" # "periodic" "nonperiodic"
PLOT_GRADIENT_CHECK = False
N_inducing_points = 30 # Number of inducing points. Wu uses 25 in 1D and 10 per dim in 2D
N_plotgridpoints = 40 # Number of grid points for plotting f posterior only 
sigma_f_fit = 8 #23.6 #8 # Variance for the tuning curve GP that is fitted. 8
delta_f_fit = 0.5 #0.6667 #0.5 # Scale for the tuning curve GP that is fitted. 0.3
min_inducing_point = 0
max_inducing_point = 2*np.pi
# For inference:
sigma_x = 5 #10.4 #5 # Variance of X for K_t
delta_x = 50 #4.5 #50 # Scale of X for K_t

print("Peyrache parameter file")