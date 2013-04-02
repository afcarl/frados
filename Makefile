# Makefile

RM=rm -f
CP=cp -f
PYTHON=python

all: wavcorr.so

clean:
	-$(RM) -r build
	-$(RM) *.pyc *.pyo
	-$(RM) wavcorr.so
	-$(RM) out.wav

wavcorr.so: wavcorr.c
	$(PYTHON) setup.py build
	$(CP) build/lib.*/wavcorr.so .

frados.py: wavcorr.so

test: frados.py
	$(PYTHON) frados.py iloveyou.wav out.wav
