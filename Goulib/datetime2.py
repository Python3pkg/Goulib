#!/usr/bin/env python
# coding: utf8
"""
additions to :mod:`datetime` standard library
"""
__author__ = "Philippe Guglielmetti"
__copyright__ = "Copyright 2012, Philippe Guglielmetti"
__credits__ = []
__license__ = "LGPL"

import six, re

from Goulib import math2, interval
from datetime import datetime,date,time,timedelta
import datetime as dt 

# classes extending builtin

class datetime2(dt.datetime):
    def __init__(self,*args,**kwargs):
        super(datetime2,self).__init__(*args,**kwargs)
    def __sub__(self,other):
        d=super(datetime2,self).__sub__(self,other)
        return timedelta(d)

class date2(dt.date):
    def init__(self,*args,**kwargs):
        super(date2,self).__init__(*args,**kwargs)

class time2(dt.time):
    def __init__(self,*args,**kwargs):
        super(time2,self).__init__(*args,**kwargs)

class timedelta2(dt.timedelta):
    def __init__(self,*args,**kwargs):
        super(timedelta2,self).__init__(*args,**kwargs)
        self.test='ok'
        
    def isoformat(self):
        #allow seamless json serialization
        return str(self)

#useful constants
timedelta0=timedelta(0) 
onesecond=timedelta(seconds=1)
oneminute=timedelta(minutes=1)
onehour=timedelta(hours=1)
oneday=timedelta(days=1)
oneweek=timedelta(weeks=1)
datemin=date(year=dt.MINYEAR,month=1,day=1)
midnight=time()

def datetimef(d,t=None,fmt='%Y-%m-%d'):
    """"converts something to a datetime
    :param d: can be:
    
    - datetime : result is a copy of d with time optionally replaced
    - date : result is date at time t, (00:00AM by default)
    - int or float : if fmt is None, d is considered as Excel date numeric format 
      (see http://answers.oreilly.com/topic/1694-how-excel-stores-date-and-time-values/ )
    - string or specified format: result is datetime parsed using specified format string
    
    :param fmt: format string. See http://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
    :param t: optional time. replaces the time of the datetime obtained from d. Allows datetimef(date,time)
    :return: datetime
    """
    if isinstance(d,dt.datetime):
        d=d
    elif isinstance(d,dt.date):
        d=datetime(year=d.year, month=d.month, day=d.day)
    elif isinstance(d,(six.integer_types,float)): 
        d=datetime(year=1900,month=1,day=1)+timedelta(days=d-2) #WHY -2 ?
    else:
        d=datetime.strptime(str(d),fmt)
    if t:
        d=d.replace(hour=t.hour,minute=t.minute,second=t.second)
    return d
    
def datef(d,fmt='%Y-%m-%d'):
    '''converts something to a date. See datetimef'''
    if isinstance(d,dt.datetime):
        return d.date()
    if isinstance(d,dt.date):
        return d
    if isinstance(d,(six.string_types,six.integer_types,float)):
        return datetimef(d,fmt=fmt).date()
    return date(d)  #last chance...
    
def timef(t,fmt='%H:%M:%S'):
    '''converts something to a time. See datetimef'''
    if isinstance(t,dt.datetime):
        return t.time()
    if isinstance(t,dt.time):
        return t
    if isinstance(t,(six.integer_types,float)):
        if not '%d' in fmt: # t is in hours
            s=math2.rint(t*3600)
            h,m=divmod(s,3600)
            m,s=divmod(m,60)
            return time(hour=h,minute=m,second=s)
        else: # t is in days (Excel
            pass
    return datetimef(t,fmt=fmt).time()
    
_cache ={}
def timedeltaf(t,fmt=None):
    '''converts something to a timedelta.
    :param t: can be:
    * already a timedelta, or a time, or a int/float giving a number of days (Excel)
    * or a string in HH:MM:SS format by default
    * or a string in timedelta str() output format
    '''
    if isinstance(t,timedelta):
        return t
    if isinstance(t,time):
        return time_sub(t,midnight)
    elif isinstance(t,(six.integer_types,float)): 
        return timedelta(days=t)
    try: #for timedeltas < 24h
        t=datetimef(t,fmt=fmt or '%H:%M:%S').time()
        return time_sub(t,midnight)
    except ValueError:
        pass
    
    # http://stackoverflow.com/questions/18303301/working-with-time-values-greater-than-24-hours
    if fmt is None:
        fmt='(%D day(s?), )?%H:%M:%S'
    if not fmt in _cache:
        expr=fmt.replace('%D','(?P<days>\d+)')
        expr=expr.replace('%H','(?P<hours>\d+)')
        expr=expr.replace('%M','(?P<minutes>\d+)')
        expr=expr.replace('%S','(?P<seconds>\d+)')
        expr='(?P<sign>-?)'+expr
        _cache[fmt]=re.compile(expr)
    try:
        expr=_cache[fmt]
        d = re.match(expr, t).groupdict(0)
    except AttributeError:
        raise ValueError('"%s" does not match fmt=%s'%(t,fmt))
    sign=d.pop('sign',None)
    td=timedelta(**dict(((key, int(value)) for key, value in d.items())))
    if sign=='-':
        td=-td
    return td

def strftimedelta(t,fmt='%H:%M:%S'):
    """
    :param t: float seconds or timedelta
    """
    if not math2.is_number(t):
        t=t.total_seconds()
    hours, remainder = divmod(t, 3600)
    minutes, seconds = divmod(remainder, 60)
    res=fmt.replace('%H','%d'%hours)
    res=res.replace('%h','%d'%hours if hours else '')
    res=res.replace('%M','%02d'%minutes)
    res=res.replace('%m','%d'%minutes if minutes else '')
    res=res.replace('%S','%02d'%seconds)
    return res

def tdround(td,s=1):
    """ return timedelta rounded to s seconds """
    return timedelta(seconds=s*round(td.total_seconds()/s))

def minutes(td):
    """
    :param td: timedelta
    :return: float timedelta in minutes
    """
    return td.total_seconds()/60.

def hours(td):
    """
    :param td: timedelta
    :return: float timedelta in hours
    """
    return td.total_seconds()/3600.

def daysgen(start,length,step=oneday):
    '''returns a range of dates or datetimes'''
    for i in range(length):
        yield start
        try:
            start=start+step
        except:
            start=time_add(start,step)
        
def days(start,length,step=oneday):
    return [x for x in daysgen(start,length,step)]

def timedelta_sum(timedeltas):
    return sum((d for d in timedeltas if d), timedelta0)

def timedelta_div(t1,t2):
    '''divides a timedelta by a timedelta or a number. 
    should be a method of timedelta...'''
    if isinstance(t2,timedelta):
        return t1.total_seconds() / t2.total_seconds()
    else:
        return timedelta(seconds=t1.total_seconds() / t2)
    
def timedelta_mul(t1,t2):
    '''multiplies a timedelta. should be a method of timedelta...'''
    try: #timedelta is t1
        return timedelta(seconds=t1.total_seconds() * t2)
    except: #timedelta is t2
        return timedelta(seconds=t2.total_seconds() * t1)
    
def time_sub(t1,t2):
    '''substracts 2 time. should be a method of time...'''
    return datetimef(datemin,t1)-datetimef(datemin,t2)

def time_add(t,d):
    '''adds delta to time. should be a method of time...'''
    return (datetimef(datemin,t)+d).time()

def add_months(date,months):
    day = date.day
    month = date.month + months - 1 #zero based
    year = date.year + month // 12
    month = month % 12 + 1 #back to 1 based
    if month == 2:
        if day >= 29 and not year%4 and (year%100 or not year%400):
            day = 29
        elif day > 28:
            day = 28
    elif month in (4,6,9,11) and day > 30:
        day = 30
    return date.replace(year, month, day)

def date_add(date,years=0,months=0,weeks=0,days=0):
    return add_months(date,years*12+months)+(weeks*7+days)*oneday

def equal(a,b,epsilon=timedelta(seconds=0.5)):
    """approximately equal. Use this instead of a==b
    :return: True if a and b are less than seconds apart
    """
    try:
        d=abs(a-b)
    except:
        d=abs(time_sub(a,b))
    return d<epsilon

def datetime_intersect(t1,t2):
    '''returns timedelta overlap between 2 intervals (tuples) of datetime'''
    a,b=interval.intersection(t1, t2)
    if not a:return timedelta0
    return b-a

def time_intersect(t1,t2):
    '''returns timedelta overlap between 2 intervals (tuples) of time'''
    a,b=interval.intersection(t1, t2)
    if not a:return timedelta0
    return time_sub(b,a)
        