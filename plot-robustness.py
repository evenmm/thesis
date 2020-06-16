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

N_seeds = 20 # that we average over
lambda_strength_array = [1.01,1.1,1.2,1.3,1.4,1.5,1.75,2,2.25,2.5,2.75,3,3.5,4,4.5,5,6,7,8,9,10]

# Mean values 
T_10 = np.load("mean_rmse_values-T-10-up-to-lambda-10.npy")
T_100 = np.load("mean_rmse_values-T-100-up-to-lambda-10.npy")
T_1000 = np.load("mean_rmse_values-T-1000-up-to-lambda-10.npy")
T_2000 = np.load("mean_rmse_values-T-2000-up-to-lambda-10.npy")
T_3162 = np.load("mean_rmse_values-T-3162-up-to-lambda-10.npy")
T_5000 = np.load("mean_rmse_values-T-5000-up-to-lambda-10.npy")

# np.std (Old)
soSqDev_10_array = np.load("std_values-T-10-up-to-lambda-10.npy")
soSqDev_100_array = np.load("std_values-T-100-up-to-lambda-10.npy")
soSqDev_1000_array = np.load("std_values-T-1000-up-to-lambda-10.npy")
soSqDev_2000_array = np.load("std_values-T-2000-up-to-lambda-10.npy")
soSqDev_3162_array = np.load("std_values-T-3162-up-to-lambda-10.npy")
soSqDev_5000_array = np.load("std_values-T-5000-up-to-lambda-10.npy")

# Sum of squared errors
#soSqDev_10_array = np.load("sum_of_squared_deviation_values-T-10-up-to-lambda-10.npy")
#soSqDev_100_array = np.load("sum_of_squared_deviation_values-T-100-up-to-lambda-10.npy")
#soSqDev_1000_array = np.load("sum_of_squared_deviation_values-T-1000-up-to-lambda-10.npy")
#soSqDev_2000_array = np.load("sum_of_squared_deviation_values-T-2000-up-to-lambda-10.npy")
#soSqDev_3162_array = np.load("sum_of_squared_deviation_values-T-3162-up-to-lambda-1.3.npy")
#soSqDev_5000_array = np.load("sum_of_squared_deviation_values-T-5000-up-to-lambda-2.npy")

colors = [plt.cm.viridis(t) for t in np.linspace(0, 1, 6)]
# 95 % confidence intervals with (20-1) degrees of freedom
# t_alpha/2 = 2.093
# S = np.sqrt(SoSqDev/(N_seeds - 1))

plt.figure()
plt.title("Average RMSE with background noise 1.0")
plt.xlabel("Expected number of spikes in a bin")
plt.ylabel("RMSE")
#### Errorbar
plt.errorbar(x=lambda_strength_array, y=T_10, yerr=(2.093*(np.sqrt(soSqDev_10_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=10", color = colors[0])
plt.errorbar(x=lambda_strength_array, y=T_100, yerr=(2.093*(np.sqrt(soSqDev_100_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=100", color = colors[1])
plt.errorbar(x=lambda_strength_array, y=T_1000, yerr=(2.093*(np.sqrt(soSqDev_1000_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=1000", color = colors[2])
plt.errorbar(x=lambda_strength_array, y=T_2000, yerr=(2.093*(np.sqrt(soSqDev_2000_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=2000", color = colors[3])
plt.errorbar(x=lambda_strength_array, y=T_3162, yerr=(2.093*(np.sqrt(soSqDev_3162_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=3162", color = colors[4])
plt.errorbar(x=lambda_strength_array, y=T_5000, yerr=(2.093*(np.sqrt(soSqDev_5000_array/(N_seeds-1)))/np.sqrt(N_seeds)), fmt="-", label="T=5000", color = colors[5])
#### Just mean
#plt.plot(lambda_strength_array, T_10, "-", label="T=10", color = colors[0])
#plt.plot(lambda_strength_array, T_100, "-", label="T=100", color = colors[1])
#plt.plot(lambda_strength_array, T_1000, "-", label="T=1000", color = colors[2])
#plt.plot(lambda_strength_array, T_2000, "-", label="T=2000", color = colors[3])
##plt.plot(lambda_strength_array, T_3162, "-", label="T=3162", color = colors[4])
##plt.plot(lambda_strength_array, T_5000, "-", label="T=5000", color = colors[5])

plt.legend(loc="upper right")
plt.ylim(ymin=0)
plt.xlim(xmin=0)
plt.xticks(range(11))
plt.tight_layout()
plt.savefig(time.strftime("./plots/%Y-%m-%d")+"-plot-robustness.png")
plt.show()





#plt.plot(lambda_strength_array, T_100 - 2.093*(np.sqrt(soSqDev_100_array/(N_seeds-1)))/np.sqrt(N_seeds), "_", label="T=100", color = colors[1])
#plt.plot(lambda_strength_array, T_100 + 2.093*(np.sqrt(soSqDev_100_array/(N_seeds-1)))/np.sqrt(N_seeds), "_", label="T=100", color = colors[1])
