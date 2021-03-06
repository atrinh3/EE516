import matplotlib.pyplot as plt
import scipy.io.wavfile as wv
import sounddevice as sd
import numpy as np
import math


def make_recording(freq, t, name):
    print("Recording...")
    s = sd.rec(int(t * freq),
               blocking=True,
               dtype='int16')
    print("Stopped recording.")
    print("Playing back recording...")
    sd.play(s, blocking=True)
    print("Playback finished.")
    # save as .wav file
    save_wav(name, s, freq)


def save_wav(filename, recording, fs):
    print("Recording saved as \"" + filename + "\".")
    wv.write(filename, fs, recording)


# The "make_window" function takes a window width parameter and returns
# an array representing the Hamming window
def make_window(w, freq):
    sample_size = int(freq * w / 1000)
    ham = []
    for n in range(0, sample_size):
        ham.append(0.54 - 0.46 * math.cos(2 * math.pi * n / sample_size))
    return ham


def make_mel_banks(min, bins, fs):
    mel_min = 1127 * math.log1p(1 + min/700)
    mel_max = 1127 * math.log1p(1 + fs/700)
    mel_banks = [float(min)]
    for i in range(1, bins+2):
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
        lo = banks[i-2]
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
    out = np.fft.fft(array, my_pad)

    # 2) take magnitude of FFT (throw away phase)
    out = abs(out)

    # create mel banks
    min = 0
    bins = 23
    mels = make_mel_banks(min, bins, fs)

    # 3) v1 compute mel filter warped spectra
    # take half of array
    tmp = len(out) / 2 + 1
    tmp = out[0:int(tmp)]

    # 5) take IDFT / DCT
    out = np.fft.irfft(mel_filter(tmp, mels, my_pad/2))

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
        tmp = np.multiply(tmp, window)
        mfcc.append(get_vector(tmp, fs, max))
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
                d.append(num/den)
    return d


# =============#
#     START    #
# -------------#
# Problem 3(a).
# Reading over MFCCs (5 points)
# Look back over the lectures and re-read precisely how MFCCs are computed.
# You’ll need to compute MFCCs using an FFT function, but you’ll also have
# to do the mel-warped frequency spectrum and the log magnitude as well.


# Problem 3(b).
# MFCC Specs (40 points)
# Write a function to take a speech utterance and compute MFCCs. You need
# only compute C0 through C12 (i.e., for each time t, you should produce
# a 13-dimensional 4 feature vector xt 2 RN with N = 13. Each time frame t
# should span a window of 25ms. Your frame rate should be 100Hz
# (i.e., a 10ms skip between frames, as is typical).

# record speech and save as .wav file
fs = 16000
time = 4
ch = 1
sd.default.samplerate = fs
sd.default.channels = ch

# filename = 'Odessa_1.wav'
# filename = 'LightsOn_1.wav'
# filename = 'LightsOff_1.wav'
# filename = 'PlayMusic_1.wav'
# filename = 'StopMusic_1.wav'
filename = 'Time_1.wav'

# make_recording(fs, time, filename)
signal = wv.read(filename)

# compute MFCCs
data = signal[1]
window = 25
framerate = 100
maxC = 12
delta_diameter = 2
hamming_window = make_window(window, fs)

# Problem 3(c). Recordings (20 points)
# Record and store as many as you can wavefiles of yourself saying the
# following single phrases: “Odessa”, “Turn on the lights”,
# “Turn off the lights”, “What time is it”, “Play music”, and “Stop music.”
# I.e., you have a six phrase vocabulary. Each wavefile should consist of
# a little bit of silence, the recording of the word, and then a bit of
# silence at the end. Make sure that the recording levels are good
# (i.e., the wavefiles should not be clipped, as that creates digital
# distortion) but also should not be too low either (as that also
# creates noise). Ideally, the peaks of the waveform should be about
# 3dB down from the maximum intensity.


# Problem 3(d).
# MFCCs (20 points)
# Compute MFCCs on each of your wavefiles and store them in separate matrices
# (the matrices will be 13 x T where T is the number of frames of speech.
mfcc = produce_mfcc(data, hamming_window, fs, framerate, maxC)

# Problem 3(e).
# Delta features (20 points)
# Once you have your matrix, compute delta features. Use a window size of M=2.
# Concatenate your feature matrix with your delta-feature matrix to create
# a feature matrix of dimension 26 x(T - 2M).
delta = get_delta(mfcc, delta_diameter)
tmp = mfcc[delta_diameter:len(mfcc)-delta_diameter]
features = []

for i in range(0, len(delta)):
    a1 = tmp[i]
    a2 = delta[i]
    test = np.concatenate((a1, a2))
    features.append(test)

# Problem 3(f).
# Question (20 points)
# Why is your matrix of dimension 26 x (T - 2M)?

# Problem 3(g).
# Turn In (5 points)
# Turn in a plot of one waveform for each speech lexical item, and also a
# plot of the corresponding 26 x (T - 2M) matrix using the matlab function
# imagesc. This means that you will turn in 5 waveforms, and 5 matrices,
# one each for each word.
plt.imshow(features, aspect='auto', cmap='jet')
plt.title('Feature matrix: Features(L), Delta(R) ')
plt.colorbar().set_label('Intensity(dB)')
plt.show()
