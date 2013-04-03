#!/usr/bin/env python
#
# frados.py
# usage: python frados.py [-d delta] input.wav out.wav
#
import sys
import wavcorr
from wavestream import WaveReader, WaveWriter


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
    
    def load(self, buf, nframes):
        #print 'detection: %s samples...' % len(wav)
        i = 0
        while i+self.wmax < nframes:
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
        self._offset += nframes
        if self._segment is not None:
            self._segment.add(self._offset, None)
            self._segment.finish()
        return

    def getsrc(self, pos):
        for seg in self.segments:
            if seg.pos0 <= pos and pos <= seg.pos1:
                return seg.getsrc(pos)
        return 0

    def getavg(self, pos):
        for seg in self.segments:
            if seg.pos0 <= pos and pos <= seg.pos1:
                return seg.getavg(pos)
        return 0


##   psola(src, framerate, pitchfuncsrc, pitchfuncdst)
##
def psola(src, framerate, pitchfuncsrc, pitchfuncdst, defaultwindow):
    nsamples = len(src)/2
    print >>sys.stderr, 'psola: %s samples...' % nsamples
    dst = ''
    psrc = 0
    pdst = 0
    window0 = defaultwindow
    while 1:
        pitchsrc = pitchfuncsrc(psrc)
        pitchdst = pitchfuncdst(pdst)
        if pitchsrc == 0 or pitchdst == 0:
            d = defaultwindow
            window1 = defaultwindow
        else:
            d = framerate/pitchsrc
            window1 = framerate/pitchdst
        if nsamples <= psrc+d: break
        #print psrc, pitchsrc, pitchdst, window1
        while d <= psrc and psrc+d < nsamples and pdst+window0+window1 < psrc:
            dst += wavcorr.psolas16(window0, psrc-d, d, src, psrc, d, src)
            #print ' ',(pdst,pdst+window0,pdst+window0+window1)
            pdst += window0
            window0 = window1
            if pitchsrc == 0: break
        psrc += d
    dst += wavcorr.psolas16(window0, psrc-d, d, src, 0, 0, src)
    return dst


# fradosify
def fradosify(path, outfp, delta):
    print >>sys.stderr, 'reading: %r' % path
    ratio = pow(2, delta/12.0)
    src = WaveReader(path)
    if src.nchannels != 1: raise ValueError('invalid number of channels')
    if src.sampwidth != 2: raise ValueError('invalid sampling width')
    dst = WaveWriter(outfp, framerate=src.framerate)
        
    buf = src.readraw()
    contour = PitchContour(src.framerate)
    contour.load(buf, src.nframes)
    def f(t):
        x = contour.getavg(t)
        if x != 0:
            x = int(x*ratio)
        return x
    dst.writeraw(psola(buf, src.framerate, contour.getsrc, f, contour.wmin))
    
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
    if not args: return usage()
    path = args.pop(0)
    if not args: return usage()
    outpath = args.pop(0)
    outfp = open(outpath, 'wb')
    fradosify(path, outfp, delta)
    outfp.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))
