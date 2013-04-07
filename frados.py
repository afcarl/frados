#!/usr/bin/env python
#
# frados.py
# usage: python frados.py [-d delta] input.wav out.wav
#

import sys
import wavcorr
from wavestream import WaveReader, WaveWriter
from pitch import PitchContour


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
