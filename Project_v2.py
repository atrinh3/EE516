# import matplotlib.pyplot as plt
import scipy.io.wavfile as wv
import sounddevice as sd
import soundfile as sf
import numpy as np
import math


def get_sign(data):
    if data >= 0:
        return 1
    return -1


def find_zeros(data):
    sum = 0
    for i in range(1, len(data)):
        a = get_sign(data[i])
        b = get_sign(data[i - 1])
        sum += int(abs(a - b) / 2)
    return sum


def get_energy(data, window):
    e = []
    i = 0
    while i + window <= len(data):
        sum = 0
        for j in range(0, int(window)):
            sum += abs(data[int(i + j)])
        e.append(sum)
        i += window
    return e


def listen(data, energy, lower, upper, frames, width, zt):
    length = len(energy)
    tmp = None
    for i in range(0, length):
        if energy[i] < lower:
            tmp = None
        if energy[i] >= lower:
            tmp = i
        if energy[i] >= upper:
            valid = zero_check(data, tmp, frames, width, zt)
            if valid is not None:
                return True
    return False


def zero_check(data, N1, frames, width, zt):
    count = 0
    least = N1 * width
    for i in range(1, frames):
        id = N1 * width - i * width
        start = int(id)
        end = int(start + width)
        # print('index %i' % i)
        # print("start %i, to end %i" % (start, end))
        if find_zeros(data[start:end]) >= math.floor(zt):
            count += 1
            if id < least:
                least = id
    if count >= 3:
        return int(least / width)
    return None


def detect_voice(signal):
    # Rabiner/Sambur Algorithm
    fs = 16000
    window = 10  # in ms
    assumed_silence = 100  # assume first 100ms is always silent
    itl = 8081
    # itu = 40407
    itu = 30000

    sample = fs * window / 1000
    energy = get_energy(signal, sample)

    # 2) Compute IMX and IMN.
    imn = energy[0]
    imx = imn
    for i in range(0, len(energy)):
        if energy[i] < imn:
            imn = energy[i]
        elif energy[i] > imx:
            imx = energy[i]

    # 3) Set ITL and ITU
    itl = min(0.03 * (imx - imn) + imn, 4 * imn)
    # itl = 0.03 * (imx - imn) + imn
    itu = 5 * itl

    # 4) Find mean and std for zero crossings
    zc_control = 25
    zc_array = []
    for i in range(0, int(assumed_silence / window)):
        start = int(i * sample)
        end = int(start + sample)
        zc_array.append(find_zeros(signal[start:end]))
    zc_mean = float(np.mean(zc_array))
    std = 0
    for i in zc_array:
        std += (i - zc_mean) * (i - zc_mean)
    std = std / len(zc_array)
    std = math.sqrt(std)
    izct = min([zc_control, zc_mean + 2 * std])

    # 5 & 6) Find N1 & N'
    intervals = 25  # frames
    return listen(signal, energy, itl, itu, intervals, sample, izct)


# The "make_window" function takes a window width parameter and returns
# an array representing the Hamming window
def make_window(w, freq):
    sample_size = int(freq * w / 1000)
    ham = []
    for n in range(0, sample_size):
        ham.append(0.54 - 0.46 * math.cos(2 * math.pi * n / sample_size))
    return ham


def make_mel_banks(min, bins, fs):
    mel_min = 1127 * math.log1p(1 + min / 700)
    mel_max = 1127 * math.log1p(1 + fs / 700)
    mel_banks = [float(min)]
    for i in range(1, bins + 2):
        mel_banks.append(i * (mel_max - mel_min) / bins)
    # inverse mel
    count = 0
    for i in mel_banks:
        mel_banks[count] = 700 * (np.exp(i / 1125) - 1)
        count += 1
    return mel_banks


def make_triangle(min, max, size, nfft, maxf):
    low = int(math.floor((nfft + 1) * min / maxf))
    high = int(math.floor((nfft + 1) * max / maxf))
    mid = int((low + high) / 2)
    triangle = []
    for i in range(0, low):
        triangle.append(0)
    for i in range(low, mid):
        id = len(triangle)
        triangle.append((id - low) / (mid - low))
    for i in range(mid, high):
        id = len(triangle)
        triangle.append((high - id) / (high - mid))
    for i in range(high, size):
        triangle.append(0)
    return triangle


def mat_multiply(a, b):
    sum = 0
    for i in range(0, len(a)):
        sum += a[i] * b[i]
    return sum


def mel_filter(data, banks, nfft):
    filtered = []
    maxf = max(banks)
    for i in range(2, len(banks)):
        lo = banks[i - 2]
        hi = banks[i]
        tri = make_triangle(lo, hi, len(data), nfft, maxf)
        coefficient = mat_multiply(data, tri)
        filtered.append(coefficient)
    # 4) take log of result
    for i in range(0, len(filtered)):
        filtered[i] = math.log10(abs(filtered[i]))
    return filtered


# have a windowed array of data points now
def get_vector(array, fs, max):
    # 1) compute FFT- Make FFT length= to next power of 2 above window length
    my_pad = int(np.power(2, 0 + np.ceil(np.log2(len(array)))))
    out = list(np.fft.fft(np.array(array), my_pad))

    # 2) take magnitude of FFT (throw away phase)
    out = np.absolute(out)

    # create mel banks
    min = 0
    bins = 23
    mels = make_mel_banks(min, bins, fs)

    # 3) v1 compute mel filter warped spectra
    # take half of array
    tmp = len(out) / 2 + 1
    tmp = out[0:int(tmp)]

    # 5) take IDFT / DCT
    out = mel_filter(tmp, mels, my_pad/2)
    # out = np.fft.irfft(out)
    # 6) retain first 13 coefficients
    return out[0:max+1]


def produce_mfcc(signal, window, fs, fr, max):
    # have a window function
    # want to apply window to signal
    # perform cepstrum operations to windowed signal
    # repeat with window shifted
    window_length = len(window)
    signal_length = len(signal)
    shift = 1 / fr * fs
    mfcc = []
    i = 0
    count = 0
    while i + window_length <= signal_length:
        # Get truncated sample and multiply with window function
        start = int(i)
        end = int(i + window_length)
        tmp = signal[start:end]
        input = []
        for j in range(0, len(tmp)):
            input.append(tmp[j] * window[j])
        mfcc.append(get_vector(input, fs, max))
        i += shift
        count += 1
    return mfcc


def get_delta(data, diameter):
    length = len(data)
    d = []
    for i in range(diameter, length - diameter):
        num = 0
        den = 0
        for j in range(-diameter, diameter + 1):
            a1 = data[i + j]
            if diameter <= j < length - diameter:
                num += np.multiply(j, a1)
                den += j * j
                d.append(num / den)
    return d


# Initializing transition probabilities so that every transition that's not
# maintaining state or going to the next state is = 0.
def get_transition(states):
    trans = []
    for i in range(0, states):
        vector = []
        for j in range(0, states):
            if i == j or j == i+1:
                vector.append(0.5)
            else:
                vector.append(0)
        trans.append(vector)
    trans[states - 1][states - 1] = 1
    return trans


# Equation from lecture 9, F58/77 & hw5.pdf equation (21)
# mean:        - Mean vector including the global mean values
# covariance:  - 1xN dim. matrix containing global covariance values
# mfcc:        - MFCC matrix of utterance
# states:      - Number of states in the HMM
def prob_observation(mean, covariance, mfcc, states):
    # mean and covariance describes the state
    observation_matrix = []
    product = 1
    for i in range(0, states):
        product = product * covariance[i]
    left = 1 / (((2 * np.pi) ** (states / 2)) * np.sqrt(product))
    for t in range(0, len(mfcc)):
        mfcc_vector = mfcc[t]
        observation_vector = []
        for q in range(0, states):
            noise = np.random.normal(0, 0.005, len(mean))
            tmp = noise + mean
            var = mfcc_vector - tmp
            sum = 0
            for i in range(0, states):
                sum += var[i] ** 2 / covariance[i]
            right = np.exp(-.5 * sum)
            observation_vector.append(left * right)
        observation_matrix.append(observation_vector)
    return observation_matrix
    # probabilty of having MFCC fector at time t for each state q


def prob_evidence(alpha):
    # p(x[1:t])
    tmp = alpha[len(alpha) - 1]
    sum = 0
    for i in range(0, len(tmp)):
        sum += tmp[i]
    return sum


# Equation from lecture 9, F58/77 & hw5.pdf equation (21)
# mean:        1 x N x Q Mean matrix that has means for each state
# covariance:  1xN dim. matrix containing global covariance values
# mfcc:        Single MFCC vector
def prob_observation_v2(means, covariances, mfcc):
    # mean and covariance describes the state
    length = len(means[0])
    product = [1] * len(means)
    for q in range(0, len(means)):
        for i in range(0, length):
            product[q] = product[q] * covariances[q][i]
    left = 1 / (((2 * np.pi) ** (length / 2)) * np.sqrt(product))
    output = []
    for q in range(0, len(means)):
        diff = np.subtract(mfcc, means[q])
        diff = np.power(diff, 2)
        diff = np.divide(diff, covariances[q])
        diff = np.sum(diff)
        right = np.exp(-0.5 * diff)
        output.append(left * right)
    return output


# Returns a vector consisting of the mean of each element of the MFCC
def get_mean(mfcc, states):
    t = len(mfcc)
    n = len(mfcc[0])
    mean = [[0] * n] * states
    for q in range(0, states):
        noise = np.random.normal(0, .05, n)
        mu_q = []
        for i in range(0, n):
            tmp = np.add(mfcc[i], noise)
            mu_q.append(np.mean(tmp))
        mean[q] = mu_q
    return mean


# This will return a 1xN covariance matrix based on the global
# MFCC values and their means.
# = sum(mfcc[t] - mean)^2 / len(mfcc)
def get_covariance(mfcc, mean):
    # MFCC is a matrix of dimension Tl x N where Tl = length of all
    # utterances combined. But since the covariance matrix will be
    # a diagonal matrix, the matrix can be condensed into a single
    # vector of length N.
    t = len(mfcc)
    n = len(mfcc[0])
    covariance = [None] * n
    m = mean[0]
    for i in range(0, n):  # 0 - 25
        sum = 0
        for j in range(0, t):  # 0 - T-1
            sum += (mfcc[j][i] - m[i]) ** 2
        covariance[i] = sum / t
    return covariance


def get_alphas(passed_mean, passed_covariance, passed_trans, passed_mfcc, states, t):
    if t < 1:
        # Reached beginning of the HMM.  Need to end the recursion
        # At the first time step, the algorithm will initialize to
        # the first state meaning q1 = 1 and all other q's = 0.
        alpha_initial = [0] * len(passed_trans[0])
        alpha_initial[0] = 1
        return [alpha_initial]
    last_alpha = get_alphas(passed_mean,
                            passed_covariance,
                            passed_trans,
                            passed_mfcc,
                            states,
                            t - 1)
    current_alpha = []
    for q in range(0, states):
        sum = 0
        for r in range(0, states):
            # q = TO state, r = FROM state
            transition_probability = passed_trans[r][q]
            sum += transition_probability * last_alpha[t - 1][r]
        observation = prob_observation_v2(passed_mean,
                                          passed_covariance,
                                          passed_mfcc[t - 1])
        current_alpha.append(observation[q] * sum)
    sum = 0
    for q in range(0, states):
        sum += current_alpha[q]
    final_out = list(np.divide(current_alpha, sum))
    # last_alpha.append(current_alpha)
    last_alpha.append(final_out)
    return last_alpha


# Equation from lecture 9, F14/77
def get_betas(passed_covar, passed_trans, passed_mfcc, states, t):
    if t > len(passed_mfcc) - 1:
        length = len(passed_trans)
        last_beta = [0] * length
        last_beta[length - 1] = 1
        return [last_beta]
    next_beta = get_betas(passed_covar, passed_trans,
                          passed_mfcc, states, t + 1)
    current_beta = []
    for i in range(0, states):
        sum = 0
        for j in range(0, states):
            # i = FROM state, j
            # = TO state
            transition_probability = passed_trans[i][j]
            sum += passed_covar[i][j] * transition_probability * next_beta[0][j]
        current_beta.append(sum)
    sum = 0
    for q in range(0, states):
        sum += current_beta[q]
    final_out = list(np.divide(current_beta, sum))
    current_beta = [final_out]
    current_beta.extend(next_beta)
    return current_beta


# Equation from lecture 9, F19/77
# alpha:       Alpha matrix
# beta:        Beta matrix
# num_states:  Number of states
# t:           Time step
def get_gamma(alpha, beta, num_states, t):
    a = alpha[t]
    b = beta[t]
    gamma = [0] * num_states
    sum = 0
    for i in range(0, num_states):
        sum += a[i] * b[i]
    for i in range(0, num_states):
        tmp = a[i] * b[i]
        tmp = tmp / sum
        gamma[i] = tmp
    return gamma


# def prob_observation_v2(mean, covariance, mfcc)
# Equation in lecture 9, F21/77
# alpha:       QxT Alpha matrix where Q = # of states
# beta:        QxT Beta matrix
# transition:  QxQ Transition matrix
# covariance:  1xN Diagaonal covariance matrix
# mfcc:        TxN MFCC matrix
# mean:        1xN Mean vector where N = number of MFCC coefficients
# states:      Number of states in HMM
# t:           Time step in the MFCC
def get_xi(alpha, beta, transition, covariance, mfcc, means, states, t):
    # observation
    mfcc_v = mfcc[t]
    p_o = prob_observation_v2(means, covariance, mfcc_v)  # 1xn
    a = alpha[t - 1]  # Qx1
    b = beta[t]  # Qx1
    e = prob_evidence(alpha)
    xi = []
    for i in range(0, states):
        tmpa = a[i]
        tmpb = b[i]
        xi_vector = []

        for j in range(0, states):
            p_transition = transition[i][j]
            xi_vector.append((p_o[i] * p_transition * tmpa * tmpb) / e)
        xi.append(xi_vector)
    return xi


def initial_state(alpha, beta, states):
    a = alpha[0]
    b = beta[0]
    sum = np.dot(a, b)
    init = []
    for i in range(0, states):
        init.append(a[i] * b[i] / sum)
    return init


def get_mfcc(waveform, hamming, fs):
    framerate = 100
    maxC = 13
    delta_diameter = 2
    mfcc = produce_mfcc(waveform, hamming, fs, framerate, maxC - 1)
    delta = get_delta(mfcc, delta_diameter)
    tmp = mfcc[delta_diameter: len(mfcc) - delta_diameter]
    features = []
    for i in range(0, len(delta)):
        features.append(np.concatenate((tmp[i], delta[i])))
    return features


def combine_mfcc(repeats, name, window, f):
    mfcc = []
    for i in range(0, repeats):
        filename = name + "_%i.wav" % (i + 1)
        data = wv.read(filename)[1]
        mfcc.extend(get_mfcc(data, window, f))
    return mfcc


def learn_initial(alphas, betas):
    out = [0] * len(alphas[0][0])
    for ell in range(0, len(alphas)):
        currenta = alphas[ell][0]
        currentb = list(betas[ell][0])
        pi = list(np.multiply(currenta, currentb))
        sum = np.sum(pi)
        out = list(np.add(out, np.divide(pi, sum)))
    out = np.divide(out, len(alphas))
    return out


# Equation 9.54 in lecture 9, F53/77
# alphas   Q x T x \ell Set of alpha matrices
# betas    Q x T x \ell Set of beta matrices
# mfccs    Set of MFCC's
# states   Number of states
def learn_transition(alphas, betas, mfccs, states,
                     means, transition_guess, covar):
    sum_transition = [[0] * states] * states
    for ell in range(0, len(alphas)):
        current_mfcc = list(mfccs[ell])
        sumg = [0] * states
        sumx = [[0] * states] * states
        for t in range(1, len(alphas[0])-1):
            currentg = get_gamma(
                alphas[ell],
                betas[ell],
                len(alphas[0][0]),
                t)
            currentx = get_xi(
                alphas[ell],
                betas[ell],
                transition_guess,
                covar,
                current_mfcc,
                means,
                states,
                t)
            for q in range(0, states):
                sumg[q] += currentg[q]
                xi_v = currentx[q]
                sumx[q] = list(np.add(sumx[q], xi_v))
        sum_transition += np.divide(sumx, sumg)
    return sum_transition / len(alphas)


# Equation 9.69 from Lecutre 9, F60/77
# alphas:        Q x T x \ell Set of alpha matrices
# betas:         Q x T x \ell Set of beta matrices
# states:        Number of states in the HMM
# mfccs:         N x T x \ell Set of \ell MFCC matrices
def learn_means(alphas, betas, states, mfccs):
    mfcc_coeffs = len(mfccs[0][0])
    sum_num = [[0] * mfcc_coeffs] * states
    sum_den = [0] * states
    for ell in range(0, len(alphas)):
        a = alphas[ell]
        b = betas[ell]
        mfcc = mfccs[ell]
        for t in range(0, len(mfcc)):
            gamma_t = get_gamma(a, b, states, t)
            x_t = mfcc[t]
            for q in range(0, states):
                state_gamma = gamma_t[q]
                sum_den[q] += state_gamma
                num = list(np.multiply(x_t, state_gamma))
                sum_num[q] = list(np.add(sum_num[q], num))
    for q in range(0, states):
        sum_num[q] = list(np.divide(sum_num[q], sum_den[q]))
    return sum_num


# Equation 9.70 from lecture 9, F60/77
# alphas:        Q x T x \ell Set of alpha matrices
# betas:         Q x T x \ell Set of beta matrices
# mfccs:         N x T x \ell Set of \ell MFCC matrices
# states:        Number of states in the HMM
# learned_mean:  1 x N x Q Set of mean MFCC values for each state
# Should end up with a 3D matrix of size N x N x Q
# i.e. Each state should have an N x N covariance matrix
# But since result will be a diagonal matrix, can be 1 x N
# This means the result will be an N x Q matrix.
def learn_covariances(alphas, betas, mfccs, states, learned_mean):
    sum_num = [[0] * len(learned_mean[0])] * states
    sum_den = [0] * states
    for ell in range(0, len(alphas)):
        mfcc = mfccs[ell]
        a = alphas[ell]
        b = betas[ell]
        for t in range(0, len(mfcc)):
            gamma_t = get_gamma(a, b, states, t)
            x_t = mfcc[t]
            for q in range(0, states):
                sum_den[q] += gamma_t[q]
                state_mean = learned_mean[q]
                diff = np.subtract(x_t, state_mean)
                var = np.power(diff, 2)
                num = list(np.multiply(var, gamma_t[q]))
                sum_num[q] = list(np.add(sum_num[q], num))
    for q in range(0, states):
        sum_num[q] = list(np.divide(sum_num[q], sum_den[q]))
    return sum_num


def check_odessa(states, means, covars, trans, init, input):
    wind = make_window(25, 16000)
    input_mfcc = get_mfcc(input, wind, 16000)
    a = get_alphas(means, covars, trans, input, states, len(input_mfcc))
    result = a[states][len(input) - 1]
    if result > .01:
        return True
    return False


def perform(data):
    lights_on_states = 20
    lights_on_trained_initial = 0
    lights_on_trained_mean = 0
    lights_on_trained_covar = 0
    lights_on_trained_trans = 0

    lights_off_states = 20
    lights_off_trained_initial = 0
    lights_off_trained_mean = 0
    lights_off_trained_covar = 0
    lights_off_trained_trans = 0

    play_music_states = 20
    play_music_trained_initial = 0
    play_music_trained_mean = 0
    play_music_trained_covar = 0
    play_music_trained_trans = 0

    stop_music_states = 20
    stop_music_trained_initial = 0
    stop_music_trained_mean = 0
    stop_music_trained_covar = 0
    stop_music_trained_trans = 0

    time_states = 20
    time_trained_initial = 0
    time_trained_mean = 0
    time_trained_covar = 0
    time_trained_trans = 0

    # do alpha recursion on input mfccs
    # check which alpha[T][N] has the highest value


def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if detect_voice(indata):
        print('Listening for "Odessa"')
        d, f = sf.read('Stream.wav')
        data = d[len(d) - 2*frames : len(d)]
        print(len(data))
        if(check_odessa(odessa_states, odessa_means_em, odessa_covariance_em,
                        odessa_transition_em, odessa_initial_em, data)):
            print("Hello, I'm Odessa")
            perform(indata)
    wavfile.write(indata)


# =============#
#     START    #
# -------------#
fs = 16000
sd.default.samplerate = fs
sd.default.channels = 1
window = 25
hamming_window = make_window(25, fs)
utterances = 1

# ===========
# EM Learning
# ===========
# Concatenating all MFCCs from ALL utterances of everything
global_mfcc = combine_mfcc(utterances, "Odessa", hamming_window, fs)
global_mfcc.extend(combine_mfcc(utterances, "LightsOn", hamming_window, fs))
global_mfcc.extend(combine_mfcc(utterances, "LightsOff", hamming_window, fs))
global_mfcc.extend(combine_mfcc(utterances, "PlayMusic", hamming_window, fs))
global_mfcc.extend(combine_mfcc(utterances, "StopMusic", hamming_window, fs))
global_mfcc.extend(combine_mfcc(utterances, "Time", hamming_window, fs))

global_mean = get_mean(global_mfcc, 1)
global_covariance = get_covariance(global_mfcc, global_mean)

# Odessa Training
odessa_states = 10
odessa_training_means = get_mean(global_mfcc, odessa_states)
odessa_alphas = [None] * utterances
odessa_betas = [None] * utterances
odessa_transition_guess = get_transition(odessa_states)
odessa_training_mfccs = []
for i in range(1, utterances + 1):
    filename = "Odessa_%i.wav" % i
    data = wv.read(filename)[1]
    odessa_training_mfccs.append(get_mfcc(data, hamming_window, fs))

for i in range(0, utterances):
    filename = "Odessa_%i.wav" % (i + 1)
    data = wv.read(filename)[1]
    tmp = get_mfcc(data, hamming_window, fs)
    odessa_alphas[i] = get_alphas(
        odessa_training_means,
        [global_covariance] * odessa_states,
        odessa_transition_guess,
        tmp,
        odessa_states,
        len(tmp))
    # print(odessa_alphas[0])
    odessa_betas[i] = get_betas(
        [global_covariance] * odessa_states,
        odessa_transition_guess,
        tmp,
        odessa_states,
        0)
    # print(odessa_betas[0])

odessa_initial_em = learn_initial(
    odessa_alphas,
    odessa_betas)
odessa_transition_em = learn_transition(
    odessa_alphas,
    odessa_betas,
    odessa_training_mfccs,
    odessa_states,
    odessa_training_means,
    odessa_transition_guess,
    [global_covariance] * odessa_states)
odessa_means_em = learn_means(
    odessa_alphas,
    odessa_betas,
    odessa_states,
    odessa_training_mfccs)
odessa_covariance_em = learn_covariances(
    odessa_alphas,
    odessa_betas,
    odessa_training_mfccs,
    odessa_states,
    odessa_means_em)

chunk = 4096
duration = 600
channels = 1
fs = 16000
filename = "Stream.wav"
sd.default.samplerate = fs
sd.default.channels = channels

wavfile = sf.SoundFile(filename,
                       mode='wb',
                       samplerate=fs,
                       channels=channels,
                       subtype='PCM_16')
print('streaming audio now...')
with sd.InputStream(callback=callback, blocksize=chunk):
    sd.sleep(int(duration * 1000))

# Write code for the data structures & algorithms of the HMMs


# Write code that computes the alpha recursion.
# Probably want to store, for each HMM, the entire alpha matrix for each word w.


# Write code that computes the beta recursion.
# Probably want to store for each HMM, the entire beta matrix for each word w.


# Create a separate alpha and beta matrix for EACH utterance of each phrase.
# Use the alpha and beta matrix to compute gamma and epsilon quantities


# From either alpha or beta matrix,
# compute probability of (x1, x2, ...,  xT) given w (p(x1:T)|w)


# Write code that computes gamma recursion.  Doesn't need to be stored since
# it's easily computed from alpha and beta matrices.


# Write code that computes epsilon quantity.  Doesn't need to be stored
# since it's easily computed from alpha and beta matrices.


# Collect set of training utterances for each word.


# Implement the EM algorithm for HMMs.


# Use the trained HMMs computed in previous steps


# ASR
