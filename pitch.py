#!/usr/bin/env python
#
# pitch.py
# usage: python pitch.py [-M|-F] [-n pitchmin] [-m pitchmax] wav ...
#

import sys
import wavcorr
from wavestream import WaveReader


##  PitchSegment
##
class PitchSegment(object):

    def __init__(self):
        self.pitches = []
        return

    def __repr__(self):
        (pos1,_) = self.pitches[-1]
        s = '-'.join( '%d-[%d]' % (pos,pitch) for (pos,pitch) in self.pitches[:-1] )
        return '(%s-%d)' % (s, pos1)

    def add(self, pos, pitch):
        self.pitches.append((pos, pitch))
        return

    def finish(self):
        self.pos0 = min( pos for (pos,_) in self.pitches )
        self.pos1 = max( pos for (pos,_) in self.pitches )
        x = 0
        for i in xrange(len(self.pitches)-1):
            (pos0,pitch0) = self.pitches[i]
            #print pos0, pitch0
            (pos1,pitch1) = self.pitches[i+1]
            x += (pitch0+pitch1)*(pos1-pos0)/2
        self.avg = x/(self.pos1-self.pos0)
        return

    def getsrc(self, pos):
        for i in xrange(len(self.pitches)-1):
            (pos0,pitch0) = self.pitches[i]
            (pos1,pitch1) = self.pitches[i+1]
            if pos0 <= pos and pos <= pos1:
                return (pos-pos0)*(pitch1-pitch0)/(pos1-pos0)+pitch0
        return 0

    def getavg(self, pos):
        return self.avg


##  PitchDetector
##
class PitchDetector(object):

    def __init__(self, framerate, pitchmin=70, pitchmax=400):
        self.framerate = framerate
        self.wmin = (framerate/pitchmax)
        self.wmax = (framerate/pitchmin)
        self.reset()
        return

    def reset(self):
        self._buf = ''
        self._nframes = 0
        return
    
    def feed(self, buf, nframes):
        self._buf += buf
        self._nframes += nframes
        i = 0
        n = self.wmin/2
        while i+self.wmax < self._nframes:
            (dmax, mmax) = wavcorr.autocorrs16(self.wmin, self.wmax, self._buf, i)
            pitch = self.framerate/dmax
            yield (n, mmax, pitch, self._buf[i*2:(i+n)*2])
            i += n
        self._buf = self._buf[i*2:]
        self._nframes -= i
        return

# main
def main(argv):
    import getopt
    def usage():
        print 'usage: %s [-M|-F] [-n pitchmin] [-m pitchmax] [-t threshold] wav ...' % argv[0]
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'MFn:m:t:')
    except getopt.GetoptError:
        return usage()
    pitchmin = 70
    pitchmax = 400
    threshold = 0.9
    bufsize = 10000
    for (k, v) in opts:
        if k == '-M': (pitchmin,pitchmax) = (75,200) # male voice
        elif k == '-F': (pitchmin,pitchmax) = (150,300) # female voice
        elif k == '-n': pitchmin = int(v)
        elif k == '-m': pitchmax = int(v)
        elif k == '-t': threshold = float(v)
    detector = None
    for path in args:
        src = WaveReader(path)
        if detector is None:
            detector = PitchDetector(src.framerate,
                                     pitchmin=pitchmin, pitchmax=pitchmax)
        i = 0
        while 1:
            (nframes,buf) = src.readraw(bufsize)
            if not nframes: break
            pitches = detector.feed(buf, nframes)
            for (n,t,freq,data) in pitches:
                if threshold <= t:
                    print i,n,t,freq
                i += n
        src.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))
