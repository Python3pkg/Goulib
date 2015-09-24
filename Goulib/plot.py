# -*- coding: utf-8 -*-
"""
plot utilities
"""
import itertools2

__author__ = "Philippe Guglielmetti"
__copyright__ = "Copyright 2015, Philippe Guglielmetti"
__credits__ = []
__license__ = "LGPL"

#import matplotlib and set backend once for all
import matplotlib, os, sys, logging

if os.getenv('TRAVIS'): # are we running https://travis-ci.org/ automated tests ?
    matplotlib.use('Agg') # Force matplotlib  not to use any Xwindows backend
elif sys.gettrace(): #http://stackoverflow.com/questions/333995/how-to-detect-that-python-code-is-being-executed-through-the-debugger
    matplotlib.use('Agg') #because 'QtAgg' crashes python while debugging
else:
    pass
    # matplotlib.use('pdf') #for high quality pdf, but doesn't work for png, svg ...
    
logging.info('matplotlib backend is %s'%matplotlib.get_backend())

from IPython.display import SVG, Image

import itertools2

def render(plotables, fmt='svg', **kwargs):
    from IPython.core.pylabtools import print_figure
    import matplotlib.pyplot as plt

    
    #extract optional arguments used for rasterization
    printargs,kwargs=itertools2.dictsplit(
        kwargs,
        ['dpi','transparent','facecolor','background']
    )
    
    ylim=kwargs.pop('ylim',None)
    title=kwargs.pop('title',None)
    
    fig, ax = plt.subplots()
    
    labels=kwargs.pop('labels',[None]*len(plotables))
    offset=kwargs.pop('offset',0) #slightly shift the points to make superimposed curves more visible
        
    for i,obj in enumerate(plotables):
        if labels[i] is None:
            try:
                labels[i]=obj._repr_latex_()
            except:
                labels[i]=str(obj)
        ax = obj._plot(ax, label=labels[i], offset=i*offset, **kwargs)       
    
    if ylim: plt.ylim(ylim)
    
    if not title and len(labels)==1:
        title=labels[0]
    if title: ax.set_title(title) 
    if len(labels)>1:
        ax.legend()
        
    data = print_figure(fig, fmt, **printargs)
    plt.close(fig)
    return data

def png(plotables, **kwargs):
    return Image(render(plotables,'png',**kwargs), embed=True)
    
def svg(plotables, **kwargs):
    return SVG(render(plotables,'svg',**kwargs))

class Plot(object):
    """base class for plotable rich object display on IPython notebooks
    inspired from http://nbviewer.ipython.org/github/ipython/ipython/blob/3607712653c66d63e0d7f13f073bde8c0f209ba8/docs/examples/notebooks/display_protocol.ipynb
    """
    
    def _plot(self, **kwargs):
        raise NotImplementedError('objects derived from plot.PLot must define a _plot method')
    
    def render(self, fmt='svg', **kwargs):
        return render([self],fmt, **kwargs) # call global function
    
    def save(self,filename,**kwargs):
        ext=filename.split('.')[-1].lower()
        kwargs.setdefault('dpi',600) #force good quality
        return open(filename,'wb').write(self.render(ext,**kwargs))
    
    def _repr_png_(self,**kwargs):
        return self.render(fmt='png',**kwargs)

    def _repr_svg_(self,**kwargs):
        return self.render(fmt='svg',**kwargs)
    
    def png(self,**kwargs):
        return Image(self._repr_png_(**kwargs), embed=True)
    
    def svg(self,**kwargs):
        return SVG(self._repr_svg_(**kwargs))
    
    