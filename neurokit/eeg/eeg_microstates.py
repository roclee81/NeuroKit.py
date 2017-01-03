"""
Microstates submodule.
"""
from ..signal import fractal_dimensions
from ..miscellaneous import find_following_duplicates

import numpy as np
import pandas as pd
import collections  # Compute frequencies
import scipy
import mne

import scipy.signal
import scipy.spatial.distance

import sklearn
import sklearn.preprocessing
import sklearn.decomposition
import sklearn.cluster
import sklearn.metrics

# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_gfp_features(data, gfp_peaks, duration, verbose=True):
    """
    Compute GFP features.
    """
    gfp_mean_peak_frequency = len(gfp_peaks)/duration
    gfp_mean_peak_duration = 1000/gfp_mean_peak_frequency
    if verbose is True:
        print("Approximately " + str(round(gfp_mean_peak_frequency, 2)) + " GFP peaks (average peak duration: " + str(round(gfp_mean_peak_duration, 2)) + " ms) per second.")
    return(gfp_mean_peak_duration)
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_gfp_peaks(data, method='GFPL1', smoothing_method=None, smoothing_window=100, peak_method="wavelet", normalize=False):
    """
    The Global Field Power (GFP) is a scalar measure of the strength of the scalp potential field and is calculated as the standard deviation of all electrodes at a given time point (Lehmann and Skrandies, 1980; Michel et al., 1993; Murray et al., 2008; Brunet et al., 2011). Between two GFP troughs, the strength of the potential field varies but the topography remains generally stable. The local maxima of the GFP are thus the best representative of a given microstate in terms of signal-to-noise ratio (Pascual-Marqui et al., 1995), corresponding to moments of high global neuronal synchronization (Skrandies, 2007).

    Parameters
    ----------
    X (ndarray):
        Array containing values for all time frames and channels.
        Dimension: number of time frames x number of channels
    method ({'GFPL1', 'GFPL2'}):
        `GFPL1` : use L1-Norm to compute GFP peaks
        `GFPL2` : use L2-Norm to compute GFP peaks
    smoothing_method ({'hamming', 'hanning'}):
            `hamming` : use hamming window to smooth
            `hanning` : use hanning window to smooth
    smoothing_window = int
        about 100
    peak_method = str
        "relative" or "wavelet"

    Returns
    ----------
        ret : ndarray
            GFP curve
    """
    ntf = data.shape[0]
    gfp = np.zeros((ntf, ))

    if method == 'GFPL2':
        for i in range(ntf):
            x = data[i,:]
            gfp[i] = np.sqrt(np.sum((x - x.mean())**2 / len(x) ))
    elif method == 'GFPL1':
        for i in range(ntf):
            x = data[i,:]
            gfp[i] = np.sum(np.abs(x - x.mean())) / len(x)

    if peak_method == "wavelet":
        gfp_peaks = np.asarray(scipy.signal.find_peaks_cwt(gfp, np.arange(1, 10)))  #we would expect a peak at about each 50 ms
    else:
        gfp_peaks = scipy.signal.argrelmax( gfp )[0]


    if smoothing_method == 'hamming':
        gfp = scipy.signal.convolve(gfp, scipy.signal.hamming(smoothing_window) )
    elif smoothing_method == 'hanning':
        gfp = scipy.signal.convolve(gfp, scipy.signal.hanning(smoothing_window) )


#    if normalize is True:
#        for i in range(data.shape[0]):
#            data[i,:] = data[i,:]/gfp[i]

    return (data, gfp, gfp_peaks)



# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_gfp_process(raws_list, names=None, scale=True):
    """
    Run the GFP analysis.
    """

    # If no names given, generate a range of ints
    if names is None:
        names = range(len(raws_list))

    # Initialize empty dict
    results = {}
    for subject in enumerate(raws_list):
        # Initialize an empty dict for each observation of the list
        results[names[subject[0]]] = {}

        # Check if MEG or EEG data
        if True in set(["MEG" in ch for ch in subject[1].info["ch_names"]]):
            meg = True
            eeg = False
        else:
            meg = False
            eeg = True

        # Save ECG channel
        try:
            results[names[subject[0]]]["ecg"] = np.array(subject[1].copy().pick_types(meg=False, eeg=False, ecg=True).to_data_frame())
        except:
            results[names[subject[0]]]["ecg"] =  np.nan

        # Select appropriate channels
        results[names[subject[0]]]["info"] = subject[1].pick_types(meg=meg, eeg=eeg).info
        data = subject[1].pick_types(meg=meg, eeg=eeg)

        # Convert to numpy array
        data = np.array(data.to_data_frame())

        # find GFP peaks
        data, gfp, gfp_peaks = eeg_gfp_peaks(data)
        results[names[subject[0]]]["microstates_times"] = gfp_peaks
        results[names[subject[0]]]["run_duration"] = len(data) / subject[1].info["sfreq"]

        # Compute and store mean GFP peak frequency
        results[names[subject[0]]]["microstates_mean_duration"] = eeg_gfp_features(data, gfp_peaks, duration=results[names[subject[0]]]["run_duration"], verbose=False)
        results[names[subject[0]]]["data_sfreq"] = subject[1].info["sfreq"]

        # Select brain state at peaks
        data_peaks = data[gfp_peaks]
        # Store the data and scale parameters
        results[names[subject[0]]]["data_scaled"] = scale
        if scale is True:
            results[names[subject[0]]]["data"] = sklearn.preprocessing.scale(data_peaks)
        else:
            results[names[subject[0]]]["data"] = data_peaks

    return(results)

# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_gmd_process():
    """
    Compute the Global Map Dissimilarity.
    """

    return()


# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_microstates_features(results, method, ecg=True, nonlinearity=True, verbose=True):
    """
    Compute statistics and features for/of the microstates.
    """

    for subject in results:

        if verbose is True:
            print("- " + subject)

        # Frequencies of each microstate
        occurences = dict(collections.Counter(results[subject]["microstates"]))

        # Compute fractal dimensions of the microstate sequence
        if nonlinearity is True:
            results[subject]["nonlinearity"] = fractal_dimensions(results[subject]["microstates"])

        results[subject]["parameters"] = {}
        # Compute parameters for each microstates:
        for microstate in set(method["microstates"]):

            results[subject]["parameters"][microstate] = {}


            try:

                # Coverage
                results[subject]["parameters"][microstate]["coverage"] = occurences[microstate]/len(results[subject]["microstates"])

                # Duration
                uniques = find_following_duplicates(results[subject]["microstates"])
                uniques_times = results[subject]["microstates_times"][np.where(uniques)]
                uniques_ms = results[subject]["microstates"][np.where(uniques)]
                times = uniques_times[np.array(np.where(uniques_ms==microstate))]
                times_1 = np.take(uniques_times, np.array(np.where(uniques_ms==microstate)) + 1, mode='clip')
                results[subject]["parameters"][microstate]["duration"] = np.mean(times_1 - times)/results[subject]["data_sfreq"]*1000

                # Occurence
                results[subject]["parameters"][microstate]["occurence"] = uniques_ms[np.array(np.where(uniques_ms==microstate))] / results[subject]["run_duration"]

            except KeyError:
                results[subject]["parameters"][microstate]["coverage"] = 0
                results[subject]["parameters"][microstate]["duration"] = np.nan

    return(results)

# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_microstates(raws, names=None, n_microstates=4, clustering_method="kmeans", scale=True, occurence_rejection_treshold=0.05, max_refitting=5, good_fit_treshold=0, feature_reduction="pca", n_features=32, nonlinearity=True, verbose=True, plot=True):
    """
    Run the full microstates analysis.
    """
    # Transform dict into list if necessary
    if isinstance(raws, dict):
        raws_list = []
        names_list= []
        for name in raws:
            names_list.append(name)
            raws_list.append(raws[name])
        if names is None:
            names = names_list


    if verbose is True:
        print("""
        STARTING MICROSTATES ANALYSIS...
        # ===================================
        1. Computing GFP peaks for each subject...
        # -----------------------------------------
        """)
    results = eeg_gfp_process(raws_list, names=names, scale=scale)

    # -------------------------------------------------------------------------
    if verbose is True:
        print("""
        2. Infering microstates pattern from all data points...
        # -----------------------------------------------------
        """)
    # Merge all data at peaks
    data_all = []
    for subject in results:
        data_all.append(results[subject]["data"])
    data_all = np.concatenate(data_all, axis=0)

    # Feature reduction
    if feature_reduction == "pca":
        if verbose is True:
            print("- Applying PCA...")
        pca = sklearn.decomposition.PCA(n_components=n_features)
        data_training = pca.fit_transform(data_all)
        explained_variance = np.sum(pca.explained_variance_ratio_)
    elif feature_reduction == "agglom":
        if verbose is True:
            print("- Applying Feature Agglomeration...")
        agglom = sklearn.cluster.FeatureAgglomeration(n_clusters=n_features)
        data_training = agglom.fit_transform(data_all)
    else:
        data_training = data_all.copy()


    # Create training set
    training_set = data_training.copy()

    if verbose is True:
        print("- Initializing the clustering algorithm...")
    if clustering_method == "kmeans":
        algorithm = sklearn.cluster.KMeans(init='k-means++', n_clusters=n_microstates, n_init=25)
    elif clustering_method == "spectral":
        algorithm = sklearn.cluster.SpectralClustering(n_clusters=n_microstates, n_init=25)
    elif clustering_method == "agglom":
        algorithm = sklearn.cluster.AgglomerativeClustering(n_clusters=n_microstates)
    else:
        print("NeuroKit Error: eeg_microstates(): clustering_method must be 'kmeans', 'spectral' or 'agglom'")



    refitting = 0  # Initialize the number of refittings
    good_fit_achieved = False
    while good_fit_achieved is False:
        good_fit_achieved = True
        if verbose is True:
            print("- Fitting the classifier...")
        # Fit the algorithm
        algorithm.fit(training_set)

        if verbose is True:
            print("- Clustering back the initial data...")
        # Predict the more likely cluster for each observation
        predicted = algorithm.predict(training_set)

        if verbose is True:
            print("- Check for abnormalities...")
        # Check for abnormalities and prune the training set until none found
        occurences = dict(collections.Counter(predicted))
        for microstate in occurences:
            # is the frequency of one microstate inferior to a treshold
            if occurences[microstate] < len(data_training)*occurence_rejection_treshold:
                good_fit_achieved = False
                refitting += 1  # Increment the refitting
                print("NeuroKit Warning: eeg_microstates(): detected some outliers: refitting the classifier (n=" + str(refitting) + ").")
                training_set = training_set[np.where(predicted!=microstate)]

    if verbose is True:
        print("- Storing the algorithm...")
    # Store results on a global level
    method = {}
    method["algorithm"] = algorithm
    method["data"] = data_all
    method["raw.info_example"] = results[subject]["info"]
    method["feature_reduction_method"] = str(feature_reduction)
    method["n_features"] = n_features
    method["clustering_method"] = clustering_method
    method["n_microstates"] = len(data_all)

    # Predict the more likely cluster for each observation on the initial set
    predicted = algorithm.predict(data_training)
    method["microstates"] = predicted



    # -------------------------------------------------------------------------
    if verbose is True:
        print("""
        3. Computing microstates features on a global level...
        # ----------------------------------------------------
        """)
    # Get metrics about the clustering
    method["silhouette_coefs"] = sklearn.metrics.silhouette_samples(data_training, predicted)  #  compute the silhouette coefficient for each data point


    # Mark as Bad the data points with bad fit index
    method["microstates_good_fit"] = np.where(method["silhouette_coefs"]>good_fit_treshold, predicted, "Bad")
    method["percentage_bad_fit"] = dict(collections.Counter(method["microstates_good_fit"]))["Bad"]/len(predicted)

    if feature_reduction is not None:
        # Plot clustering result on the two first features
        if plot is True:
            to_plot = pd.DataFrame({"Princomp1": data_training[:, 0], "Princomp3": data_training[:, 2],"Princomp2": data_training[:, 1], "Princomp4": data_training[:, 3], "Cluster": method["microstates_good_fit"]})
            pd.tools.plotting.radviz(to_plot, "Cluster")


    # -------------------------------------------------------------------------
    if verbose is True:
        print("""
        4. Computing microstates features on a local level...
        # ---------------------------------------------------
        """)
    # Store results for each run
    # Generate index attributing each point of the predicted data to its subject number
    index = []
    for subject in results:
        index += [subject] * len(results[subject]["data"])

    # For each subject, select the appropriate part of the predicted sequence and store it
    for subject in results:
        results[subject]["microstates"] = method["microstates"][np.where(np.array(index)==subject)]


    results = eeg_microstates_features(results, method, nonlinearity=nonlinearity, verbose=verbose)

    if verbose is True:
        print("""
        5. Done.
        # ------
        """)
    return(results, method)




# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
def eeg_plot_microstates(method, path="", extension=".png", explicit_name=False, show_sensors_position=False, show_sensors_name=False, plot=True, save=True, dpi=300, contours=3, colorbar=False):
    """
    Plot the microstates.
    """
    figures = []
    for microstate in set(method["microstates_good_fit"]):
        if microstate != "Bad":
            values = np.mean(method["data"][np.where(method["microstates_good_fit"] == microstate)], axis=0)
            values = np.array(values, ndmin=2).T
            evoked = mne.EvokedArray(values, method["raw.info_example"], 0)
            fig = evoked.plot_topomap(times=0, title=microstate, size=6, contours=contours, time_format="", show=plot, colorbar=colorbar, show_names=show_sensors_name, sensors=show_sensors_position)

            figures.append(fig)

            if save is True:
                if explicit_name is False:
                    name = path + "microstate_" + microstate + extension
                else:
                    name = path + "microstate_" + microstate + "_" + method["n_microstates"] + "_" + method["feature_reduction_method"] + method["n_features"] + "_" + method["clustering_method"] + extension
                fig.savefig(name, dpi=dpi)
    return(figures)