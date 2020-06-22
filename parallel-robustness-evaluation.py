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
from function_library import * # loglikelihoods, gradients, covariance functions, tuning curve definitions
#from parameter_file import * # where all the parameters are set (Not needed because importing in function library)
from posterior_f_inference import *

#################################
##### Robustness evaluation #####
#################################

## Set T and choose an array of lambda peak strengths
## For each lambda peak strength: Run 20 seeds
## For each seed, the best RMSE is taken from an ensemble of 5 initializations with different wmoothingwindow in the PCA


# History: branched off from em-algorithm on 11.05.2020
# and from robust-sim-data on 28.05.2020
# then from robust-efficient-script on 30.05.2020

######################################
## RMSE function                    ##
######################################
def find_rmse_for_this_lambda_this_seed(seedindex):
    print("Seed", seeds[seedindex], "started.")
    peak_f_offset = np.log(peak_lambda_global) - baseline_f_value
    np.random.seed(seeds[seedindex])
    # Generate path
    path = (upper_domain_limit-lower_domain_limit)/2 + numpy.random.multivariate_normal(np.zeros(T), K_t_generate)
    #path = np.linspace(lower_domain_limit, upper_domain_limit, T)
    if KEEP_PATH_INSIDE_DOMAIN_BY_FOLDING:
        # Use boolean masks to keep X within min and max of tuning 
        path -= lower_domain_limit # bring path to 0
        modulo_two_pi_values = path // (upper_domain_limit)
        oddmodulos = (modulo_two_pi_values % 2).astype(bool)
        evenmodulos = np.invert(oddmodulos)
        # Even modulos: Adjust for being outside
        path[evenmodulos] -= upper_domain_limit*modulo_two_pi_values[evenmodulos]
        # Odd modulos: Adjust for being outside and flip for continuity
        path[oddmodulos] -= upper_domain_limit*(modulo_two_pi_values[oddmodulos])
        differences = upper_domain_limit - path[oddmodulos]
        path[oddmodulos] = differences
        path += lower_domain_limit # bring path back to min value for tuning
    if SCALE_UP_PATH_TO_COVER_DOMAIN:
        # scale to cover the domain:
        path -= min(path)
        path /= max(path)
        path *= (upper_domain_limit-lower_domain_limit)
        path += lower_domain_limit
    if PLOTTING:
        ## plot path 
        if T > 100:
            plt.figure(figsize=(10,3))
        else:
            plt.figure()
        plt.plot(path, color="black", label='True X') #plt.plot(path, '.', color='black', markersize=1.) # trackingtimes as x optional
        #plt.plot(trackingtimes-trackingtimes[0], path, '.', color='black', markersize=1.) # trackingtimes as x optional
        plt.xlabel("Time bin")
        plt.ylabel("x")
        plt.title("True path of X")
        plt.ylim((lower_domain_limit, upper_domain_limit))
        plt.tight_layout()
        plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T)  + "-seed-" + str(seeds[seedindex]) + "-path.png")
    ## Generate spike data. True tuning curves are defined here
    if TUNINGCURVE_DEFINITION == "triangles":
        tuningwidth = 1 # width of tuning (in radians)
        biasterm = -2 # Average H outside tuningwidth -4
        tuningcovariatestrength = np.linspace(0.5*tuningwidth,10.*tuningwidth, N) # H value at centre of tuningwidth 6*tuningwidth
        neuronpeak = [min_neural_tuning_X + (i+0.5)/N*(max_neural_tuning_X - min_neural_tuning_X) for i in range(N)]
        true_f = np.zeros((N, T))
        y_spikes = np.zeros((N, T))
        for i in range(N):
            for t in range(T):
                if COVARIANCE_KERNEL_KX == "periodic":
                    distancefrompeaktopathpoint = min([ abs(neuronpeak[i]+2.*pi-path[t]),  abs(neuronpeak[i]-path[t]),  abs(neuronpeak[i]-2.*pi-path[t]) ])
                elif COVARIANCE_KERNEL_KX == "nonperiodic":
                    distancefrompeaktopathpoint = abs(neuronpeak[i]-path[t])
                Ht = biasterm
                if(distancefrompeaktopathpoint < tuningwidth):
                    Ht = biasterm + tuningcovariatestrength[i] * (1-distancefrompeaktopathpoint/tuningwidth)
                true_f[i,t] = Ht
                # Spiking
                if LIKELIHOOD_MODEL == "bernoulli":
                    spike_probability = exp(Ht)/(1.+exp(Ht))
                    y_spikes[i,t] = 1.0*(rand()<spike_probability)
                    # If you want to remove randomness: y_spikes[i,t] = spike_probability
                elif LIKELIHOOD_MODEL == "poisson":
                    spike_rate = exp(Ht)
                    y_spikes[i,t] = np.random.poisson(spike_rate)
                    # If you want to remove randomness: y_spikes[i,t] = spike_rate
    elif TUNINGCURVE_DEFINITION == "bumps":
        true_f = np.zeros((N, T))
        y_spikes = np.zeros((N, T))
        for i in range(N):
            for t in range(T):
                true_f[i,t] = bumptuningfunction(path[t], i, peak_f_offset)
                if LIKELIHOOD_MODEL == "bernoulli":
                    spike_probability = exp(true_f[i,t])/(1.+exp(true_f[i,t]))
                    y_spikes[i,t] = 1.0*(rand()<spike_probability)
                elif LIKELIHOOD_MODEL == "poisson":
                    spike_rate = exp(true_f[i,t])
                    y_spikes[i,t] = np.random.poisson(spike_rate)
    if PLOTTING:
        ## Plot true f in time
        plt.figure()
        color_idx = np.linspace(0, 1, N)
        plt.title("True log tuning curves f")
        plt.xlabel("x")
        plt.ylabel("f value")
        x_space_grid = np.linspace(lower_domain_limit, upper_domain_limit, T)
        for i in range(N):
            plt.plot(x_space_grid, true_f[i], linestyle='-', color=plt.cm.viridis(color_idx[i]))
        plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-true-f.png")
    if PLOTTING:
        ## Plot firing rate h in time
        plt.figure()
        color_idx = np.linspace(0, 1, N)
        plt.title("True firing rate h")
        plt.xlabel("x")
        plt.ylabel("Firing rate")
        x_space_grid = np.linspace(lower_domain_limit, upper_domain_limit, T)
        for i in range(N):
            plt.plot(x_space_grid, np.exp(true_f[i]), linestyle='-', color=plt.cm.viridis(color_idx[i]))
        plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-true-h.png")
    ###############################
    # Covariance matrix Kgg_plain #
    ###############################
    # Inducing points based on a predetermined range
    x_grid_induce = np.linspace(min_inducing_point, max_inducing_point, N_inducing_points) #np.linspace(min(path), max(path), N_inducing_points)
    #print("Min and max of path:", min(path), max(path))
    #print("Min and max of grid:", min(x_grid_induce), max(x_grid_induce))
    K_gg_plain = squared_exponential_covariance(x_grid_induce.reshape((N_inducing_points,1)),x_grid_induce.reshape((N_inducing_points,1)), sigma_f_fit, delta_f_fit)
    ######################
    # Initialize X and F #
    ######################
    # Here the PCA ensemble comes into play:
    ensemble_array_X_rmse = np.zeros(len(ensemble_smoothingwidths))
    ensemble_array_X_estimate = np.zeros((len(ensemble_smoothingwidths), T))
    ensemble_array_F_estimate = np.zeros((len(ensemble_smoothingwidths), N, T))
    ensemble_array_y_spikes = np.zeros((len(ensemble_smoothingwidths), N, T))
    ensemble_array_path = np.zeros((len(ensemble_smoothingwidths), T))
    for smoothingwindow_index in range(len(ensemble_smoothingwidths)):
        smoothingwindow_for_PCA = ensemble_smoothingwidths[smoothingwindow_index]
        # PCA initialization: 
        celldata = zeros(shape(y_spikes))
        for i in range(N):
            celldata[i,:] = scipy.ndimage.filters.gaussian_filter1d(y_spikes[i,:], smoothingwindow_for_PCA) # smooth
            #celldata[i,:] = (celldata[i,:]-mean(celldata[i,:]))/std(celldata[i,:])                 # standardization requires at least one spike
        X_pca_result = PCA(n_components=1, svd_solver='full').fit_transform(transpose(celldata))
        X_pca_initial = np.zeros(T)
        for i in range(T):
            X_pca_initial[i] = X_pca_result[i]
        # Scale PCA initialization to fit domain:
        X_pca_initial -= min(X_pca_initial)
        X_pca_initial /= max(X_pca_initial)
        X_pca_initial *= (upper_domain_limit-lower_domain_limit)
        X_pca_initial += lower_domain_limit
        # Flip PCA initialization correctly by comparing to true path
        X_pca_initial_flipped = 2*mean(X_pca_initial) - X_pca_initial
        X_pca_initial_rmse = np.sqrt(sum((X_pca_initial-path)**2) / T)
        X_pca_initial_flipped_rmse = np.sqrt(sum((X_pca_initial_flipped-path)**2) / T)
        if X_pca_initial_flipped_rmse < X_pca_initial_rmse:
            X_pca_initial = X_pca_initial_flipped
        # Scale PCA initialization to fit domain:
        X_pca_initial -= min(X_pca_initial)
        X_pca_initial /= max(X_pca_initial)
        X_pca_initial *= (upper_domain_limit-lower_domain_limit)
        X_pca_initial += lower_domain_limit
        if PLOTTING:
            # Plot PCA initialization
            if T > 100:
                plt.figure(figsize=(10,3))
            else:
                plt.figure()
            plt.xlabel("Time bin")
            plt.ylabel("x")
            plt.title("PCA initial of X")
            plt.plot(path, color="black", label='True X')
            plt.plot(X_pca_initial, label="Initial")
            plt.legend(loc="upper right")
            plt.tight_layout()
            plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + "-PCA-initial.png")
        # Initialize X
        np.random.seed(0)
        if X_initialization == "true":
            X_initial = path
        if X_initialization == "ones":
            X_initial = np.ones(T)
        if X_initialization == "pca":
            X_initial = X_pca_initial
        if X_initialization == "randomrandom":
            X_initial = (upper_domain_limit - lower_domain_limit)*np.random.random(T)
        if X_initialization == "randomprior":
            X_initial = (upper_domain_limit - lower_domain_limit)*np.random.multivariate_normal(np.zeros(T), K_t_generate)
        if X_initialization == "linspace":
            X_initial = np.linspace(lower_domain_limit, upper_domain_limit, T) 
        X_estimate = np.copy(X_initial)
        # Initialize F
        F_initial = np.sqrt(y_spikes) - np.amax(np.sqrt(y_spikes))/2 #np.log(y_spikes + 0.0008)
        F_estimate = np.copy(F_initial)
        if GIVEN_TRUE_F:
            F_estimate = true_f
        if PLOTTING:
            if T > 100:
                plt.figure(figsize=(10,3))
            else:
                plt.figure()
            #plt.title("Path of X")
            plt.title("X estimate")
            plt.xlabel("Time bin")
            plt.ylabel("x")
            plt.plot(path, color="black", label='True X')
            plt.plot(X_initial, label='Initial')
            #plt.legend(loc="upper right")
            #plt.ylim((lower_domain_limit, upper_domain_limit))
            plt.tight_layout()
            plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + ".png")
        if PLOT_GRADIENT_CHECK:
            sigma_n = np.copy(global_initial_sigma_n)
            # Adding tiny jitter term to diagonal of K_gg (not the same as sigma_n that we're adding to the diagonal of K_xgK_gg^-1K_gx later on)
            K_gg = K_gg_plain + jitter_term*np.identity(N_inducing_points) ##K_gg = K_gg_plain + sigma_n*np.identity(N_inducing_points)
            X_gradient = x_jacobian_no_la(X_estimate, sigma_n, F_estimate, K_gg, x_grid_induce)
            if T > 100:
                plt.figure(figsize=(10,3))
            else:
                plt.figure()
            plt.xlabel("Time bin")
            plt.ylabel("x")
            plt.title("Gradient at initial X")
            plt.plot(path, color="black", label='True X')
            plt.plot(X_initial, label="Initial")
            #plt.plot(X_gradient, label="Gradient")
            plt.plot(X_estimate + 2*X_gradient/max(X_gradient), label="Gradient plus offset")
            plt.legend(loc="upper right")
            plt.tight_layout()
            plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + "-Gradient.png")
            exit()
            """
            print("Testing gradient...")
            #X_estimate = path
            #F_estimate = true_f
            print("Gradient difference using check_grad:",scipy.optimize.check_grad(func=x_posterior_no_la, grad=x_jacobian_no_la, x0=path, args=(sigma_n, F_estimate, K_gg, x_grid_induce)))

            #optim_gradient = optimization_result.jac
            print("Epsilon:", np.sqrt(np.finfo(float).eps))
            optim_gradient1 = scipy.optimize.approx_fprime(xk=X_estimate, f=x_posterior_no_la, epsilon=1*np.sqrt(np.finfo(float).eps), args=(sigma_n, F_estimate, K_gg, x_grid_induce))
            optim_gradient2 = scipy.optimize.approx_fprime(xk=X_estimate, f=x_posterior_no_la, epsilon=x_posterior_no_la, 1e-4, args=(sigma_n, F_estimate, K_gg, x_grid_induce))
            optim_gradient3 = scipy.optimize.approx_fprime(xk=X_estimate, f=x_posterior_no_la, epsilon=x_posterior_no_la, 1e-2, args=(sigma_n, F_estimate, K_gg, x_grid_induce))
            optim_gradient4 = scipy.optimize.approx_fprime(xk=X_estimate, f=x_posterior_no_la, epsilon=x_posterior_no_la, 1e-2, args=(sigma_n, F_estimate, K_gg, x_grid_induce))
            calculated_gradient = x_jacobian_no_la(X_estimate, sigma_n, F_estimate, K_gg, x_grid_induce)
            difference_approx_fprime_1 = optim_gradient1 - calculated_gradient
            difference_approx_fprime_2 = optim_gradient2 - calculated_gradient
            difference_approx_fprime_3 = optim_gradient3 - calculated_gradient
            difference_approx_fprime_4 = optim_gradient4 - calculated_gradient
            difference_norm1 = np.linalg.norm(difference_approx_fprime_1)
            difference_norm2 = np.linalg.norm(difference_approx_fprime_2)
            difference_norm3 = np.linalg.norm(difference_approx_fprime_3)
            difference_norm4 = np.linalg.norm(difference_approx_fprime_4)
            print("Gradient difference using approx f prime, epsilon 1e-8:", difference_norm1)
            print("Gradient difference using approx f prime, epsilon 1e-4:", difference_norm2)
            print("Gradient difference using approx f prime, epsilon 1e-2:", difference_norm3)
            print("Gradient difference using approx f prime, epsilon 1e-2:", difference_norm4)
            plt.figure()
            plt.title("Gradient compared to numerical gradient")
            plt.plot(calculated_gradient, label="Analytic")
            #plt.plot(optim_gradient1, label="Numerical 1")
            plt.plot(optim_gradient2, label="Numerical 2")
            plt.plot(optim_gradient3, label="Numerical 3")
            plt.plot(optim_gradient4, label="Numerical 4")
            plt.legend()
            plt.figure()
            #plt.plot(difference_approx_fprime_1, label="difference 1")
            plt.plot(difference_approx_fprime_2, label="difference 2")
            plt.plot(difference_approx_fprime_3, label="difference 3")
            plt.plot(difference_approx_fprime_4, label="difference 4")
            plt.legend()
            plt.show()
            exit()
            """
        #############################
        # Iterate with EM algorithm #
        #############################
        prev_X_estimate = np.Inf
        sigma_n = np.copy(global_initial_sigma_n)
        for iteration in range(N_iterations):
            if iteration > 0:
                sigma_n = sigma_n * lr  # decrease the noise variance with a learning rate
                if LET_INDUCING_POINTS_CHANGE_PLACE_WITH_X_ESTIMATE:
                    x_grid_induce = np.linspace(min(X_estimate), max(X_estimate), N_inducing_points) # Change position of grid to position of estimate
            # Adding tiny jitter term to diagonal of K_gg (not the same as sigma_n that we're adding to the diagonal of K_xgK_gg^-1K_gx later on)
            K_gg = K_gg_plain + jitter_term*np.identity(N_inducing_points) ##K_gg = K_gg_plain + sigma_n*np.identity(N_inducing_points)
            K_xg_prev = squared_exponential_covariance(X_estimate.reshape((T,1)),x_grid_induce.reshape((N_inducing_points,1)), sigma_f_fit, delta_f_fit)
            # Find F estimate only if we're not at the first iteration
            if iteration > 0:
                if LIKELIHOOD_MODEL == "bernoulli":
                    for i in range(N):
                        y_i = y_spikes[i]
                        optimization_result = optimize.minimize(fun=f_loglikelihood_bernoulli, x0=F_estimate[i], jac=f_jacobian_bernoulli, args=(sigma_n, y_i, K_xg_prev, K_gg), method = 'L-BFGS-B', options={'disp':False}) #hess=f_hessian_bernoulli, 
                        F_estimate[i] = optimization_result.x
                elif LIKELIHOOD_MODEL == "poisson":
                    for i in range(N):
                        y_i = y_spikes[i]
                        optimization_result = optimize.minimize(fun=f_loglikelihood_poisson, x0=F_estimate[i], jac=f_jacobian_poisson, args=(sigma_n, y_i, K_xg_prev, K_gg), method = 'L-BFGS-B', options={'disp':False}) #hess=f_hessian_poisson, 
                        F_estimate[i] = optimization_result.x 
            # Find next X estimate, that can be outside (0,2pi)
            if GIVEN_TRUE_F: 
                print("NB! NB! We're setting the f value to the optimal F given the path.")
                F_estimate = np.copy(true_f)
            if NOISE_REGULARIZATION:
                X_estimate += 2*np.random.multivariate_normal(np.zeros(T), K_t_generate) - 1
            if SMOOTHING_REGULARIZATION and iteration < (N_iterations-1) :
                X_estimate = scipy.ndimage.filters.gaussian_filter1d(X_estimate, 4)
            if GRADIENT_FLAG: 
                optimization_result = optimize.minimize(fun=x_posterior_no_la, x0=X_estimate, args=(sigma_n, F_estimate, K_gg, x_grid_induce), method = "L-BFGS-B", jac=x_jacobian_no_la, options = {'disp':False})
            else:
                optimization_result = optimize.minimize(fun=x_posterior_no_la, x0=X_estimate, args=(sigma_n, F_estimate, K_gg, x_grid_induce), method = "L-BFGS-B", options = {'disp':False})
            X_estimate = optimization_result.x
            if (iteration == (FLIP_AFTER_HOW_MANY - 1)) and FLIP_AFTER_SOME_ITERATION:
                # Flipping estimate after iteration 1 has been plotted
                X_estimate = 2*mean(X_estimate) - X_estimate
            if USE_OFFSET_AND_SCALING_AT_EVERY_ITERATION:
                X_estimate -= min(X_estimate) #set offset of min to 0
                X_estimate /= max(X_estimate) #scale length to 1
                X_estimate *= (max(path)-min(path)) #scale length to length of path
                X_estimate += min(path) #set offset to offset of path
            if PLOTTING:
                plt.plot(X_estimate, label='Estimate')
                #plt.ylim((lower_domain_limit, upper_domain_limit))
                plt.tight_layout()
                plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + ".png")
            if np.linalg.norm(X_estimate - prev_X_estimate) < TOLERANCE:
                #print("Seed", seeds[seedindex], "Iterations:", iteration+1, "Change in X smaller than TOL")
                break
            #if iteration == N_iterations-1:
            #    print("Seed", seeds[seedindex], "Iterations:", iteration+1, "N_iterations reached")
            prev_X_estimate = X_estimate
        if USE_OFFSET_AND_SCALING_AFTER_CONVERGENCE:
            X_estimate -= min(X_estimate) #set offset of min to 0
            X_estimate /= max(X_estimate) #scale length to 1
            X_estimate *= (max(path)-min(path)) #scale length to length of path
            X_estimate += min(path) #set offset to offset of path
        # Flipped 
        X_flipped = - X_estimate + 2*mean(X_estimate)
        # Rootmeansquarederror for X
        X_rmse = np.sqrt(sum((X_estimate-path)**2) / T)
        X_flipped_rmse = np.sqrt(sum((X_flipped-path)**2) / T)
        ##### Check if flipped and maybe iterate again with flipped estimate
        if X_flipped_rmse < X_rmse:
            #print("RMSE for X:", X_rmse)
            #print("RMSE for X flipped:", X_flipped_rmse)
            #print("Re-iterating because of flip")
            x_grid_induce = np.linspace(min_inducing_point, max_inducing_point, N_inducing_points) #np.linspace(min(path), max(path), N_inducing_points)
            K_gg_plain = squared_exponential_covariance(x_grid_induce.reshape((N_inducing_points,1)),x_grid_induce.reshape((N_inducing_points,1)), sigma_f_fit, delta_f_fit)
            X_initial_2 = np.copy(X_flipped)
            X_estimate = np.copy(X_flipped)
            F_estimate = np.copy(F_initial)
            if GIVEN_TRUE_F:
                F_estimate = true_f
            if PLOTTING:
                if T > 100:
                    plt.figure(figsize=(10,3))
                else:
                    plt.figure()
                #plt.title("After flipping") # as we go
                plt.xlabel("Time bin")
                plt.ylabel("x")
                plt.plot(path, color="black", label='True X')
                plt.plot(X_initial_2, label='Initial')
                #plt.ylim((lower_domain_limit, upper_domain_limit))
                plt.tight_layout()
                plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + "-flipped.png")
            #############################
            # EM after flipped          #
            #############################
            prev_X_estimate = np.Inf
            sigma_n = np.copy(global_initial_sigma_n)
            for iteration in range(N_iterations):
                if iteration > 0:
                    sigma_n = sigma_n * lr  # decrease the noise variance with a learning rate
                    if LET_INDUCING_POINTS_CHANGE_PLACE_WITH_X_ESTIMATE:
                        x_grid_induce = np.linspace(min(X_estimate), max(X_estimate), N_inducing_points) # Change position of grid to position of estimate
                # Adding tiny jitter term to diagonal of K_gg (not the same as sigma_n that we're adding to the diagonal of K_xgK_gg^-1K_gx later on)
                K_gg = K_gg_plain + jitter_term*np.identity(N_inducing_points) ##K_gg = K_gg_plain + sigma_n*np.identity(N_inducing_points)
                K_xg_prev = squared_exponential_covariance(X_estimate.reshape((T,1)),x_grid_induce.reshape((N_inducing_points,1)), sigma_f_fit, delta_f_fit)
                # Find F estimate only if we're not at the first iteration
                if iteration > 0:
                    if LIKELIHOOD_MODEL == "bernoulli":
                        for i in range(N):
                            y_i = y_spikes[i]
                            optimization_result = optimize.minimize(fun=f_loglikelihood_bernoulli, x0=F_estimate[i], jac=f_jacobian_bernoulli, args=(sigma_n, y_i, K_xg_prev, K_gg), method = 'L-BFGS-B', options={'disp':False}) #hess=f_hessian_bernoulli, 
                            F_estimate[i] = optimization_result.x
                    elif LIKELIHOOD_MODEL == "poisson":
                        for i in range(N):
                            y_i = y_spikes[i]
                            optimization_result = optimize.minimize(fun=f_loglikelihood_poisson, x0=F_estimate[i], jac=f_jacobian_poisson, args=(sigma_n, y_i, K_xg_prev, K_gg), method = 'L-BFGS-B', options={'disp':False}) #hess=f_hessian_poisson, 
                            F_estimate[i] = optimization_result.x 
                # Find next X estimate, that can be outside (0,2pi)
                if GIVEN_TRUE_F: 
                    print("NB! NB! We're setting the f value to the optimal F given the path.")
                    F_estimate = np.copy(true_f)
                if NOISE_REGULARIZATION:
                    X_estimate += 2*np.random.multivariate_normal(np.zeros(T), K_t_generate) - 1
                if SMOOTHING_REGULARIZATION and iteration < (N_iterations-1) :
                    X_estimate = scipy.ndimage.filters.gaussian_filter1d(X_estimate, 4)
                if GRADIENT_FLAG: 
                    optimization_result = optimize.minimize(fun=x_posterior_no_la, x0=X_estimate, args=(sigma_n, F_estimate, K_gg, x_grid_induce), method = "L-BFGS-B", jac=x_jacobian_no_la, options = {'disp':False})
                else:
                    optimization_result = optimize.minimize(fun=x_posterior_no_la, x0=X_estimate, args=(sigma_n, F_estimate, K_gg, x_grid_induce), method = "L-BFGS-B", options = {'disp':False})
                X_estimate = optimization_result.x
                if (iteration == (FLIP_AFTER_HOW_MANY - 1)) and FLIP_AFTER_SOME_ITERATION:
                    # Flipping estimate after iteration 1 has been plotted
                    X_estimate = 2*mean(X_estimate) - X_estimate
                if USE_OFFSET_AND_SCALING_AT_EVERY_ITERATION:
                    X_estimate -= min(X_estimate) #set offset of min to 0
                    X_estimate /= max(X_estimate) #scale length to 1
                    X_estimate *= (max(path)-min(path)) #scale length to length of path
                    X_estimate += min(path) #set offset to offset of path
                if PLOTTING:
                    plt.plot(X_estimate, label='Estimate (after flip)')
                    #plt.ylim((lower_domain_limit, upper_domain_limit))
                    plt.tight_layout()
                    plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-robust-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + "-flipped.png")
                if np.linalg.norm(X_estimate - prev_X_estimate) < TOLERANCE:
                    #print("Seed", seeds[seedindex], "Iterations after flip:", iteration+1, "Change in X smaller than TOL")
                    break
                #if iteration == N_iterations-1:
                #    print("Seed", seeds[seedindex], "Iterations after flip:", iteration+1, "N_iterations reached")
                prev_X_estimate = X_estimate
            if USE_OFFSET_AND_SCALING_AFTER_CONVERGENCE:
                X_estimate -= min(X_estimate) #set offset of min to 0
                X_estimate /= max(X_estimate) #scale length to 1
                X_estimate *= (max(path)-min(path)) #scale length to length of path
                X_estimate += min(path) #set offset to offset of path
                # Check if flipped is better even after flipped convergence:
                X_flipped = - X_estimate + 2*mean(X_estimate)
                # Rootmeansquarederror for X
                X_rmse = np.sqrt(sum((X_estimate-path)**2) / T)
                X_flipped_rmse = np.sqrt(sum((X_flipped-path)**2) / T)
                ##### Check if flipped and maybe iterate again with flipped estimate
                if X_flipped_rmse < X_rmse:
                    X_estimate = X_flipped
            # Rootmeansquarederror for X
            X_rmse = np.sqrt(sum((X_estimate-path)**2) / T)
        #print("Seed", seeds[seedindex], "smoothingwindow", smoothingwindow_for_PCA, "finished. RMSE for X:", X_rmse)
        #SStot = sum((path - mean(path))**2)
        #SSdev = sum((X_estimate-path)**2)
        #Rsquared = 1 - SSdev / SStot
        #Rsquared_values[seed] = Rsquared
        #print("R squared value of X estimate:", Rsquared, "\n")
        #####
        # Rootmeansquarederror for F
        #if LIKELIHOOD_MODEL == "bernoulli":
        #    h_estimate = np.divide( np.exp(F_estimate), (1 + np.exp(F_estimate)))
        #if LIKELIHOOD_MODEL == "poisson":
        #    h_estimate = np.exp(F_estimate)
        #F_rmse = np.sqrt(sum((h_estimate-true_f)**2) / (T*N))
        if PLOTTING:
            if T > 100:
                plt.figure(figsize=(10,3))
            else:
                plt.figure()
            plt.title("Final estimate") # as we go
            plt.xlabel("Time bin")
            plt.ylabel("x")
            plt.plot(path, color="black", label='True X')
            plt.plot(X_initial, label='Initial')
            plt.plot(X_estimate, label='Estimate')
            plt.legend(loc="upper right")
            #plt.ylim((lower_domain_limit, upper_domain_limit))
            plt.tight_layout()
            plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-paral-T-" + str(T) + "-lambda-" + str(peak_lambda_global) + "-background-" + str(baseline_lambda_value) + "-seed-" + str(seeds[seedindex]) + "-final.png")
        ensemble_array_X_rmse[smoothingwindow_index] = X_rmse
        ensemble_array_X_estimate[smoothingwindow_index] = X_estimate
        ensemble_array_F_estimate[smoothingwindow_index] = F_estimate
        ensemble_array_y_spikes[smoothingwindow_index] = y_spikes
        ensemble_array_path[smoothingwindow_index] = path
        # Finish loop for one smoothingwidth
    # Find best rmse across smoothingwindows for PCA start:
    best_rmse_index = np.argmin(ensemble_array_X_rmse)
    X_rmse = ensemble_array_X_rmse[best_rmse_index]
    X_estimate = ensemble_array_X_estimate[best_rmse_index]
    F_estimate = ensemble_array_F_estimate[best_rmse_index]
    y_spikes = ensemble_array_y_spikes[best_rmse_index]
    path = ensemble_array_path[best_rmse_index]
    print("Seed", seeds[seedindex], "RMSEs", ensemble_array_X_rmse, "\nBest smoothing window:", ensemble_smoothingwidths[best_rmse_index], "with RMSE:", X_rmse)
    return [X_rmse, X_estimate, F_estimate, y_spikes, path]

if __name__ == "__main__": 
    print("Likelihood model:",LIKELIHOOD_MODEL)
    print("Covariance kernel for Kx:", COVARIANCE_KERNEL_KX)
    print("Using gradient?", GRADIENT_FLAG)
    print("Noise regulation:",NOISE_REGULARIZATION)
    print("Initial sigma_n:", global_initial_sigma_n)
    print("Learning rate:", lr)
    print("T:", T)
    print("N:", N)
    print("Smoothingwidths:", ensemble_smoothingwidths)
    if FLIP_AFTER_SOME_ITERATION:
        print("NBBBB!!! We're flipping the estimate in line 600.")
    print("\n")

    seed_rmse_array = np.zeros(len(seeds))
    X_array = np.zeros((len(seeds), T))
    F_array = np.zeros((len(seeds), N, T))
    Y_array = np.zeros((len(seeds), N, T))
    path_array = np.zeros((len(seeds), T))

    # We gather the mean rmse values for each tuning strength in this array:
    mean_rmse_values = np.zeros(len(peak_lambda_array))
    sum_of_squared_deviation_values = np.zeros(len(peak_lambda_array))
    for lambda_index in range(len(peak_lambda_array)):
        global peak_lambda_global
        peak_lambda_global = peak_lambda_array[lambda_index]

        # Pool computing
        print("Time to make a pool")
        starttime = time.time()
        myPool = Pool(processes=len(seeds))
        result_array = myPool.map(find_rmse_for_this_lambda_this_seed, [i for i in range(len(seeds))])
        myPool.close()
        endtime = time.time()

        # Unpack results
        for i in range(len(seeds)):
            seed_rmse_array[i] = result_array[i][0]
            X_array[i] = result_array[i][1]
            F_array[i] = result_array[i][2]
            Y_array[i] = result_array[i][3]
            path_array[i] = result_array[i][4]
        mean_rmse_values[lambda_index] = np.mean(seed_rmse_array)
        sum_of_squared_deviation_values[lambda_index] = sum((seed_rmse_array - np.mean(seed_rmse_array))**2)
        np.save("mean_rmse_values-base-lambda-" + str(baseline_lambda_value) + "T-" + str(T) + "-up-to-lambda-" + str(peak_lambda_global), mean_rmse_values)
        np.save("sum_of_squared_deviation_values-base-lambda-" + str(baseline_lambda_value) + "T-" + str(T) + "-up-to-lambda-" + str(peak_lambda_global), sum_of_squared_deviation_values)

        print("\n")
        print("Lambda strength:", peak_lambda_global)
        #print("Array of rmse for seeds:", seed_rmse_array)
        print("RMSE for X, Averaged across seeds:", mean_rmse_values[lambda_index])
        print("STD for RMSE:", sum_of_squared_deviation_values[lambda_index])
        print("Time use:", endtime - starttime)
        print("\n")

    if INFER_F_POSTERIORS:
        posterior_f_inference(F_array[0], 1, Y_array[0], path_array[0] , X_array[0])

