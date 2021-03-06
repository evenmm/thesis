from scipy import *
import scipy.io
import scipy.ndimage
import numpy as np
import scipy.optimize as optimize
import numpy.random
import matplotlib
#matplotlib.use('Agg') # When running on cluster, plots cannot be shown and this must be used
import matplotlib.pyplot as plt
import time
import sys
plt.rc('image', cmap='viridis')
numpy.random.seed(13)

###############################
## Inference of tuning curves #
###############################
## Using Gaussian Processes ###
###############################


##############
# Parameters #
##############
offset = 1000 # Starting point in observed X values
T = 1000
sigma_fit = 8 # Variance for the GP that is fitted
delta_fit = 0.3 # Scale for the GP that is fitted
sigma_epsilon_fit = 0.2 # Assumed variance of observations for the GP that is fitted
X_dim = 40 # Number of grid points

"""
sigma_Kx = 8 # variance of kx
delta_Kx = 0.3 # length scale of kx
Kx = Kx + np.identity(T)*10e-5 # To be able to invert Kx we add a small amount on the diagonal
"""

##############################
# Data fetch and definitions #
##############################

name = sys.argv[1] #'Mouse28-140313_stuff_BS0030_awakedata.mat'

sigma = 10 # window for smoothing
thresholdforneuronstokeep = 1000 # number of spikes to be considered useful

mat = scipy.io.loadmat(name)
headangle = ravel(array(mat['headangle']))
cellspikes = array(mat['cellspikes'])
cellnames = array(mat['cellnames'])
trackingtimes = ravel(array(mat['trackingtimes']))

## make matrix of spikes
startt = min(trackingtimes)
binsize = mean(trackingtimes[1:]-trackingtimes[:(-1)])
nbins = len(trackingtimes)
binnedspikes = zeros((len(cellnames), nbins))
sgood = zeros(len(binnedspikes[:,0]))<1
for i in range(len(cellnames)):
  spikes = ravel((cellspikes[0])[i])
  for j in range(len(spikes)):
    # note 1ms binning means that number of ms from start is the correct index
    tt = int(floor(  (spikes[j] - startt)/float(binsize)  ))
    if(tt>nbins-1 or tt<0): # check if outside bounds of the awake time
      continue
    binnedspikes[i,tt] += 1 # add a spike to the thing

  ## check if actvitity is ok
  if(sum(binnedspikes[i,:])<thresholdforneuronstokeep):
      sgood[i] = False
      continue

binnedspikes = binnedspikes[sgood,:]
cellnames = cellnames[sgood]

# Remove nan items
whiches = np.isnan(headangle)
headangle = headangle[~whiches]
binnedspikes = binnedspikes[:,~whiches]

# Select part of data to be able to make X
path = headangle[offset:offset+T]
binnedspikes = binnedspikes[:,offset:offset+T]
binnedspikes = (binnedspikes>0)*1 #Reset to ones 

if (sum(isnan(path)) > 0):
    print("\nXXXXXXXXX\nXXXXXXXXX\nXXXXXXXXX\nThere are NAN values in path\nXXXXXXXXX\nXXXXXXXXX\nXXXXXXXXX")

N = len(cellnames) #51 with cutoff at 1000 spikes
print("T:",T)
print("N:",N)
print("How many times are there more than one spike:", sum((binnedspikes>1)*1))
y_spikes = binnedspikes
print("mean(y_spikes)",mean(y_spikes))

## plot head direction 
plt.figure(figsize=(10,2))
plt.plot(path, '.', color='black', markersize=1.)
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-headdirection.png")


def exponential_covariance(t1,t2, sigma, delta):
    distance = abs(t1-t2)
    return sigma * exp(-distance/delta)

def gaussian_periodic_covariance(x1,x2, sigma, delta):
    distancesquared = min([(x1-x2)**2, (x1+2*pi-x2)**2, (x1-2*pi-x2)**2])
    return sigma * exp(-distancesquared/(2*delta))

def gaussian_NONPERIODIC_covariance(x1,x2, sigma, delta):
    distancesquared = (x1-x2)**2
    return sigma * exp(-distancesquared/(2*delta))

###############################
## Inference of tuning curves #
###############################

N_observations = T
x_values_observed = path
print("Making spatial covariance matrice: Kx_fit at observations")
Kx_fit_at_observations = np.zeros((N_observations,N_observations))
for x1 in range(N_observations):
    for x2 in range(N_observations):
        Kx_fit_at_observations[x1,x2] = gaussian_periodic_covariance(x_values_observed[x1],x_values_observed[x2], sigma_fit, delta_fit)
# By adding sigma_epsilon on the diagonal, we assume noise and make the covariance matrix positive semidefinite
Kx_fit_at_observations = Kx_fit_at_observations  + np.identity(N_observations)*sigma_epsilon_fit
Kx_fit_at_observations_inverse = np.linalg.inv(Kx_fit_at_observations)
fig, ax = plt.subplots()
kx_obs_mat = ax.matshow(Kx_fit_at_observations, cmap=plt.cm.Blues)
fig.colorbar(kx_obs_mat, ax=ax)
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-hd-inference-Kx_fit_at_observations.png")

# NEGATIVE Loglikelihood of f given X (since we minimize it to maximize the loglikelihood)
def f_loglikelihood_bernoulli(f_i):
    likelihoodterm = sum( np.multiply(y_i, (f_i - np.log(1+np.exp(f_i)))) + np.multiply((1-y_i), np.log(1- np.divide(np.exp(f_i), 1 + np.exp(f_i)))))
    priorterm = - 0.5*np.dot(f_i, np.dot(Kx_fit_at_observations_inverse, f_i))
    return - (likelihoodterm + priorterm)

def f_jacobian_bernoulli(f_i):
    e_tilde = np.divide(exp(f_i), 1 + exp(f_i))
    f_derivative = y_i - e_tilde - np.dot(Kx_fit_at_observations_inverse, f_i)
    return - f_derivative

def f_hessian_bernoulli(f_i):
    e_plain_fraction = np.divide(exp(f_i), (1 + exp(f_i))**2)
    f_hessian = - np.diag(e_plain_fraction) - Kx_fit_at_observations_inverse 
    return - f_hessian

## Optimization of f given X
print("Optimizing...\n(This should be parallelized)\n")
starttime = time.time()
f_tuning_curve = np.zeros(shape(y_spikes)) #np.sqrt(y_spikes) # Initialize f values
for i in range(N):
    y_i = y_spikes[i]
    optimization_result = optimize.minimize(f_loglikelihood_bernoulli, f_tuning_curve[i], jac=f_jacobian_bernoulli, hess=f_hessian_bernoulli, method = 'L-BFGS-B', options={'disp':False})
    f_tuning_curve[i] = optimization_result.x
endtime = time.time()
print("Time spent:", "{:.2f}".format(endtime - starttime))

#################################################
# Find posterior prediction of log tuning curve #
#################################################
bins = np.linspace(-0.000001, 2.*np.pi+0.0000001, num=X_dim + 1)
x_grid = 0.5*(bins[:(-1)]+bins[1:])
f_values_observed = f_tuning_curve

print("Making spatial covariance matrice: Kx crossover")
Kx_crossover = np.zeros((N_observations,X_dim))
for x1 in range(N_observations):
    for x2 in range(X_dim):
        Kx_crossover[x1,x2] = gaussian_periodic_covariance(x_values_observed[x1],x_grid[x2], sigma_fit, delta_fit)
fig, ax = plt.subplots()
kx_cross_mat = ax.matshow(Kx_crossover, cmap=plt.cm.Blues)
fig.colorbar(kx_cross_mat, ax=ax)
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-hd-inference-kx_crossover.png")
Kx_crossover_T = np.transpose(Kx_crossover)
print("Making spatial covariance matrice: Kx grid")
Kx_grid = np.zeros((X_dim,X_dim))
for x1 in range(X_dim):
    for x2 in range(X_dim):
        Kx_grid[x1,x2] = gaussian_periodic_covariance(x_grid[x1],x_grid[x2], sigma_fit, delta_fit)
fig, ax = plt.subplots()
kxmat = ax.matshow(Kx_grid, cmap=plt.cm.Blues)
fig.colorbar(kxmat, ax=ax)
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-hd-inference-kx_grid.png")

# Infer mean on the grid
pre = np.zeros((N,T))
mu_posterior = np.zeros((N, X_dim))
for i in range(N):
    pre[i] = np.dot(Kx_fit_at_observations_inverse, f_values_observed[i])
    mu_posterior[i] = np.dot(Kx_crossover_T, pre[i])
# Calculate standard deviations
sigma_posterior = (Kx_grid) - np.dot(Kx_crossover_T, np.dot(Kx_fit_at_observations_inverse, Kx_crossover))
fig, ax = plt.subplots()
sigma_posteriormat = ax.matshow(sigma_posterior, cmap=plt.cm.Blues)
fig.colorbar(sigma_posteriormat, ax=ax)
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-hd-inference-sigma_posterior.png")

###############################################
# Plot tuning curve with confidence intervals #
###############################################
standard_deviation = np.sqrt(np.diag(sigma_posterior))
upper_confidence_limit = mu_posterior + 1.96*standard_deviation
lower_confidence_limit = mu_posterior - 1.96*standard_deviation

h_estimate = np.exp(mu_posterior)/ (1 + np.exp(mu_posterior))
h_upper_confidence_limit = np.exp(upper_confidence_limit) / (1 + np.exp(upper_confidence_limit))
h_lower_confidence_limit = np.exp(lower_confidence_limit) / (1 + np.exp(lower_confidence_limit))

## Find observed firing rate
observed_spikes = zeros((N, X_dim))
for i in range(N):
    for x in range(X_dim):
        timesinbin = (path>bins[x])*(path<bins[x+1])
        if(sum(timesinbin)>0):
            observed_spikes[i,x] = mean( y_spikes[i, timesinbin] )
        else:
            print("No observations of X between",bins[x],"and",bins[x+1],".")
colors = [plt.cm.viridis(t) for t in np.linspace(0, 1, N)]
for n4 in range(N//4):
    plt.figure(figsize=(10,8))
    neuron = np.array([[0,1],[2,3]])
    neuron = neuron + 4*n4
    for i in range(2):
        for j in range(2):
            plt.subplot(2,2,i*2+j+1)
            plt.plot(x_grid, observed_spikes[neuron[i,j],:], color="#cfb302")
            plt.plot(x_grid, h_estimate[neuron[i,j],:], color=colors[0]) 
            plt.plot(x_grid, h_upper_confidence_limit[neuron[i,j],:], "--", color=colors[0])
            plt.plot(x_grid, h_lower_confidence_limit[neuron[i,j],:], "--", color=colors[0])
            plt.ylim(0.,1.)
            plt.title(neuron[i,j]+1)
    plt.savefig(time.strftime("./plots/%Y-%m-%d")+"hd-fitted-tuning"+str(n4+1)+".png")
plt.show()
