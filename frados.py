#!/usr/bin/env python
#
# frados.py
# usage: python frados.py [-d delta] input.wav out.wav
#
import sys
import wave
import array
import wavcorr
from wavestream import WaveReader, WaveWriter
from math import pi, cos, sqrt

# vector functions (numpy would be recommended)
try:
    import numpy
    def mkarray(x):
        return numpy.array(x)
    def add(x, y):
        return numpy.add(x,y)
    def multiply(x, y):
        return numpy.multiply(x,y)
    def dot(x, y):
        return numpy.dot(x,y)
    def hanning(n):
        return numpy.hanning(n)
except ImportError:
    def mkarray(x):
        return list(x)
    def add(x, y):
        return [ a+b for (a,b) in zip(x,y) ]
    def multiply(x, y):
        return [ a*b for (a,b) in zip(x,y) ]
    def dot(x, y):
        return sum( a*b for (a,b) in zip(x,y) )
    def hanning(n):
        C = 2*pi/(n-1)
        return [ (1.0-cos(C*i))*0.5 for i in xrange(n) ]


##  PitchContour
##
class PitchContour(object):

    class Segment(object):

        def __init__(self):
            self.pitches = []
            return

        def __repr__(self):
            (pos1,_) = self.pitches[-1]
            s = '-'.join( '%d-[%d]' % (pos,pitch) for (pos,pitch) in self.pitches[:-1] )
            return '(%s-%d)' % (s, pos1)

        def add(self, pos, pitch):
            if pitch is None:
                (_,pitch) = self.pitches[-1]
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
            print self
            return

        def getsrc(self, pos):
            for i in xrange(len(self.pitches)-1):
                (pos0,pitch0) = self.pitches[i]
                (pos1,pitch1) = self.pitches[i+1]
                if pos0 <= pos and pos <= pos1:
                    return (pos-pos0)*(pitch1-pitch0)/(pos1-pos0)+pitch0
            return None

        def getavg(self, pos):
            return self.avg

    def __init__(self, framerate,
                 pitchmin=100, pitchmax=240, threshold=0.7):
        self.framerate = framerate
        self.wmin = (framerate/pitchmax)
        self.wmax = (framerate/pitchmin)
        self.threshold = threshold
        self.segments = []
        self._offset = 0
        self._segment = None
        return
    
    def load(self, wav):
        #print 'detection: %s samples...' % len(wav)
        i = 0
        buf = wav.readraw()
        while i < len(wav):
            (dmax, mmax) = wavcorr.autocorrs16(self.wmin, self.wmax, buf, i)
            if self.threshold < mmax:
                pitch = self.framerate/dmax
                if self._segment is None:
                    self._segment = self.Segment()
                    self.segments.append(self._segment)
                self._segment.add(self._offset+i, pitch)
                i += self.wmin/2
            else:
                if self._segment is not None:
                    self._segment.add(self._offset+i, None)
                    self._segment.finish()
                    self._segment = None
                i += self.wmin/2
        self._offset += len(wav)
        if self._segment is not None:
            self._segment.add(self._offset, None)
            self._segment.finish()
        return

    def getsrc(self, pos):
        for seg in self.segments:
            if seg.pos0 <= pos and pos <= seg.pos1:
                return seg.getsrc(pos)
        return None

    def getavg(self, pos):
        for seg in self.segments:
            if seg.pos0 <= pos and pos <= seg.pos1:
                return seg.getavg(pos)
        return None


##   psola(src, framerate, pitchfuncsrc, pitchfuncdst)
##
def psola(src, framerate, pitchfuncsrc, pitchfuncdst, defaultwindow):
    
    def stretch(src, n1):
        n0 = len(src)
        return [ src[i*n0/n1] for i in xrange(n1) ]

    def put(dst, i, src):
        n = min(len(src), len(dst)-i)
        if 0 < n:
            dst[i:i+n] = add(dst[i:i+n], src[:n])
        return

    print >>sys.stderr, 'psola: %s samples...' % len(src)
    dst = [ 0.0 for _ in xrange(len(src)) ]
    psrc = 0
    pdst = 0
    window0 = 0
    while 1:
        pitchsrc = pitchfuncsrc(psrc)
        pitchdst = pitchfuncdst(pdst)
        if pitchsrc is None or pitchdst is None:
            d = defaultwindow
            window1 = defaultwindow
        else:
            d = framerate/pitchsrc
            window1 = framerate/pitchdst
        if len(src) <= psrc+d: break
        #print psrc, pitchsrc, pitchdst, window1
        while d <= psrc and pdst+window0+window1 < psrc:
            hann0 = hanning(window0*2)[:window0]
            hann1 = hanning(window1*2)[window1:]
            a0 = multiply(stretch(src[psrc-d:psrc], window0), hann0)
            a1 = multiply(stretch(src[psrc:psrc+d], window1), hann1)
            #print ' ',(pdst,pdst+window0,pdst+window0+window1)
            put(dst, pdst, a0)
            pdst += window0
            put(dst, pdst, a1)
            window0 = window1
            if pitchsrc is None: break
        psrc += d
    return dst


# fradosify
def fradosify(path, outfp, delta):
    print >>sys.stderr, 'reading: %r' % path
    ratio = pow(2, delta/12.0)
    src = WaveReader(path)
    if src.nchannels != 1: raise ValueError('invalid number of channels')
    if src.sampwidth != 2: raise ValueError('invalid sampling width')
    dst = WaveWriter(outfp, framerate=src.framerate)
        
    contour = PitchContour(src.framerate)
    contour.load(src)
    def f(t):
        x = contour.getavg(t)
        if x is not None:
            x = int(x*ratio)
        return x
    src.seek(0)
    dst.write(psola(src.read(), src.framerate, contour.getsrc, f, contour.wmin))
    
    src.close()
    dst.close()
    return

# main
def main(argv):
    import getopt
    def usage():
        print 'usage: %s [-d delta] input.wav output.wav' % argv[0]
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'd:')
    except getopt.GetoptError:
        return usage()
    delta = +8
    for (k, v) in opts:
        if k == '-d': delta = int(v)
    if len(args) < 2: return usage()
    path = args.pop(0)
    outpath = args.pop(0)
    outfp = open(outpath, 'wb')
    fradosify(path, outfp, delta)
    outfp.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))
