import os
import sys
import json
import glob
import math
import fnmatch
import subprocess
import numpy as np


def mp3_to_wav(mp3file, wavfile):
    ffmpeg = subprocess.Popen(('ffmpeg.exe', '-i', mp3file, '-y', '-ac', '1', wavfile), stderr=subprocess.PIPE)
    ffmpeg.communicate()
    ffmpeg.stderr.close()

def wave_data(wavfile):
    return np.fromfile(open(wavfile), np.int16)[24:]

def waveform(mp3file, output_dir=None, length=1200, max_value=255):
    wavfile = mp3file.rpartition('.')[0] + '.wav'
    if output_dir:
        wavfile = os.path.join(output_dir, os.path.split(wavfile)[1])
    mp3_to_wav(mp3file, wavfile)

    data = wave_data(wavfile)
    data = np.absolute(data)

    os.remove(wavfile)

    results = []
    size = data.size / length
    for i in range(0, length):
        total = np.sum(np.power(data[i * size: (i * size) + size], 2, dtype=np.double), dtype=np.double)
        result = math.sqrt(total / data.size)
        if np.isnan(result):
            result = sys.maxint
        results.append(result)

    scale = max_value / max(results)
    return [int(i * scale) for i in results]

def main(argv):
    input_dir, output_dir = argv

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print 'Indexing..',
    mp3files = []
    for root, dirnames, filenames in os.walk(input_dir):
        for filename in fnmatch.filter(filenames, '*.mp3'):
            path = os.path.join(root, filename)
            if os.path.getsize(path) > 0:
                mp3files.append(os.path.join(root, path))
    print 'Done!'

    num_mp3files = len(mp3files)
    for index, mp3file in enumerate(mp3files):
        jsonfile = mp3file.rpartition('.')[0] + '.json'
        jsonfile = os.path.join(output_dir, os.path.split(jsonfile)[1])
        if not os.path.exists(jsonfile):
            with open(jsonfile, 'wb') as fp:
                fp.write(json.dumps(waveform(mp3file, output_dir=output_dir)))
        sys.stdout.write('\rGenerated %d/%d waveforms(s).. ' % (index + 1, num_mp3files))
        sys.stdout.flush()
    print 'Done!'

    print 'Collecting results..',
    results = {}
    for path in glob.glob(os.path.join(output_dir, '*.json')):
        try:
            id = int(os.path.split(path)[1][:-5])
        except:
            continue
        with open(path) as fp:
            results[id] = json.load(fp)
    with open(os.path.join(output_dir, 'results.json'), 'wb') as fp:
        json.dump(results, fp)
    print 'Done!'

if __name__ == "__main__":
    main(sys.argv[1:])

