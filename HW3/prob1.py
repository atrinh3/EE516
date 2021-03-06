import matplotlib.pyplot as plt
import numpy as np
import scipy.io.wavfile as wv
import sounddevice as sd


def make_recording(freq, time, name):
    print("Recording...")
    s = sd.rec(int(time * fs),
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


def make_spectrogram(s, nfft, npower, fs, row, id, fig, ax):
    # Now produce a spectrogram.
    my_pad = int(np.power(2, (npower - 1) + np.ceil(np.log2(nfft))))

    # Note that my_pad is a power of 2, and this is what the final FFT length
    # python will use.

    # Next, we set how many points of the speech windows overlap between successive
    # windows. We’re going to say that 7/8’ths of the points overlap (so stepping
    # by 1/8th of a window at each column of the spectrogram. Note that
    # how many points this is depends on the window size.
    my_noverlap = int(float(nfft) * 7.0 / 8.0)

    # Lastly, we’re going to select a color map. ’jet’ has commonly been used
    # in matlab, but there is some concern about using ’jet’ as a color map as
    # the color intensity (or luminosity) is dark for both low and high magnitude
    # values (so it doesn’t plot well when plotted in B&W). Hence, we’re going
    # to use the colormap called ’cubehelix’, although if you change this to
    # use ’jet’, you’ll see results that probably look more familiar since ’jet’
    # is so widely used when plotting in color.
    my_cmap = plt.get_cmap('cubehelix')

    # Lastly, plot the spectrogram.
    axes = ax[row-1, npower-1]
    axes.specgram(
        s[1],
        NFFT=nfft,
        Fs=fs,
        pad_to=my_pad,
        noverlap=my_noverlap,
        cmap=my_cmap)
    print("debug")


def prob_1_a(w, data, fs, row, figure, ax):
    fft = int(float(fs) * float(w) / 1000.0)
    for i in range(1, 5):
        id = (row - 1) * 4 + i
        make_spectrogram(data, fft, i, fs, row, id, figure, ax)


# =============#
#    START    #
# -------------#
fs = 16000  # 16kHz sample rate
duration = 4  # 4 seconds
filename = "Odessa_1.wav"
sd.default.samplerate = fs
sd.default.channels = 1
row = 5
col = 4

# make_recording(fs, duration, filename)
signal = wv.read(filename)

# print(type(signal))
# print(type(signal[1]))

fig, ax = plt.subplots(row, col, sharex='all', sharey='all')
fig.set_size_inches(6, 8)
# print(ax.shape[0]) # 5
# print(ax.shape[1]) # 4

# for i in range(1, ax.shape[0]+1):
#     prob_1_a(5, signal, fs, i, fig, ax)
prob_1_a(5, signal, fs, 1, fig, ax)
prob_1_a(10, signal, fs, 2, fig, ax)
prob_1_a(25, signal, fs, 3, fig, ax)
prob_1_a(50, signal, fs, 4, fig, ax)
prob_1_a(100, signal, fs, 5, fig, ax)

fig.suptitle('Spectrogram Grid')
plt.show()

# Prob 1a
# try window sizes 5, 10, 25, 50, 100 (ms)
# for each window size, use increasing power of 2 for FFT size
# should have 20 spectrograms at the end

# window size 5 = 80 samples
# FFT 1 = 128
# FFT 2 = 256
# FFT 3 = 512
# FFT 4	= 1024

# window size 10 = 160 samples
# FFT 1 = 256
# FFT 2 = 512
# FFT 3 = 1024
# FFT 4 = 2048

# window size 25 = 400 samples
# FFT 1 = 512
# FFT 2 = 1024
# FFT 3 = 2048
# FFT 4 = 4096

# window size 50 = 800 samples
# FFT 1 = 1024
# FFT 2 = 2048
# FFT 3 = 4096
# FFT 4 = 8192

# window size 100 = 1600 samples
# FFT 1 = 2048
# FFT 2 = 4096
# FFT 3 = 8192
# FFT 4 = 16384
