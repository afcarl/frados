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
    srcwindow0 = 0
    dstwindow0 = 0
    while 1:
        pitchsrc = pitchfuncsrc(psrc)
        pitchdst = pitchfuncdst(pdst)
        if pitchsrc == 0 or pitchdst == 0:
            srcwindow1 = defaultwindow
            dstwindow1 = defaultwindow
        else:
            srcwindow1 = framerate/pitchsrc/2
            dstwindow1 = framerate/pitchdst/2
        if nsamples <= psrc+srcwindow1: break
        dst += wavcorr.psolas16(dstwindow1,
                                psrc, srcwindow1, src,
                                psrc, srcwindow1, src)
        pdst += dstwindow1
        psrc += srcwindow1
        print pitchsrc, pitchdst, (psrc, srcwindow1, dstwindow1)
        (srcwindow0,dstwindow0) = (srcwindow1,dstwindow1)
        continue
        #print psrc, pitchsrc, pitchdst, window1
        while srcwindow <= psrc and psrc+srcwindow < nsamples and pdst+dstwindow0+dstwindow1 < psrc:
            dst += wavcorr.psolas16(dstwindow0,
                                    psrc-srcwindow, srcwindow, src,
                                    psrc-srcwindow, srcwindow, src)
            #print ' ',(pdst,pdst+dstwindow0,pdst+dstwindow0+dstwindow1)
            pdst += dstwindow0
            dstwindow0 = dstwindow1
            if pitchsrc == 0: break
        psrc += srcwindow
    return dst


# fradosify
def fradosify(path, outfp, delta,
              pitchmin=70, pitchmax=400, threshold=0.7):
    print >>sys.stderr, 'reading: %r' % path
    ratio = pow(2, delta/12.0)
    src = WaveReader(path)
    if src.nchannels != 1: raise ValueError('invalid number of channels')
    if src.sampwidth != 2: raise ValueError('invalid sampling width')
    contour = PitchContour(
        src.framerate,
        pitchmin=pitchmin, pitchmax=pitchmax,
        threshold=threshold)

    dst = WaveWriter(outfp, framerate=src.framerate)

    nframes = src.nframes
    buf = src.readraw(nframes)
    contour.reset()
    contour.load(buf, nframes)
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
        print 'usage: %s [-M|-F] [-t threshold] [-d delta] input.wav output.wav' % argv[0]
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'MFt:d:')
    except getopt.GetoptError:
        return usage()
    delta = +8
    pitchmin = 70
    pitchmax = 400
    threshold = 0.9
    for (k, v) in opts:
        if k == '-M': (pitchmin,pitchmax) = (75,200) # male voice
        elif k == '-F': (pitchmin,pitchmax) = (150,300) # female voice
        elif k == '-t': threshold = float(v)
        elif k == '-d': delta = int(v)
    if not args: return usage()
    path = args.pop(0)
    if not args: return usage()
    outpath = args.pop(0)
    outfp = open(outpath, 'wb')
    fradosify(path, outfp, delta,
              pitchmin=pitchmin, pitchmax=pitchmax, threshold=threshold)
    outfp.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))
