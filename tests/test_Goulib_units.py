#!/usr/bin/env python
# coding: utf8
from nose.tools import assert_equal
from nose import SkipTest
#lines above are inserted automatically by pythoscope. Line below overrides them
from Goulib.tests import *

from Goulib.units import *

class Tests:
    def test_append_col(self):
        # assert_equal(expected, appendCol(self, colname, values))
        raise SkipTest 

    def test001_simple_value(self):
        ureg.define('CHF = [Currency]')
        ureg.define('EUR = 1.21*CHF')
        ureg.define('USD = 0.93*CHF')
        dist = V(1000,'m')
        assert_equal(str(dist),'1000 meter')
        speed = V(10,'m/s')
        assert_equal(str(speed),'10 meter / second')
        time = dist/speed
        assert_equal(str(time),'100.0 second')
        hourlyRate = V(50,'USD/hour')
        cost = hourlyRate*time
        assert_equal('{:f}'.format(cost.to('CHF')),'1.291667 CHF') #warning : Py2 and Py3 have different precision for str(float)

    def test002_table(self):
        t = Table(   'mytable',      ['car',          'bus',                                     'pedestrian'],
                  [  'speed',        V(120,'km/hour'), V(100,'km/hour'),                          V(5,'km/hour'),
                     'acceleration', V(1,'m/s^2'),     V(0.1,'m/s^2'),                            V(0.2,'m/s^2'),
                     'autonomy',     V(600,'km'),      lambda: t['autonomy']['pedestrian']*10,    lambda: t['speed']['pedestrian']*V(6,'hour') #coucou
                  ])
        assert_count_equal(t.cols,['car',        'bus',         'pedestrian'])
        assert_count_equal(t.rowLabels,['speed','acceleration','autonomy'])
        from pprint import pformat#otherwise it takes Goulib.tests.pprint...
        logging.debug(pformat(t.rows))
        assert_equal(t['speed']['bus'],V(100,'km/hour'))
        logging.debug(t._repr_html_())
        
        v = View(t,rows=['autonomy','speed'],cols=['car','pedestrian'],rowUnits={'speed':'mile/hour'},name='my view')
        logging.debug(v._repr_html_())
        
        t.appendCol('cheval',{'speed':V(60,'km/hour'),'acceleration':V(0.3,'m/s^2'),'autonomy':V(40,'km')})
        logging.debug(t._repr_html_())
        
        t.appendRow('length', [V(4552,'mm'), V(20,'m'), V(50,'cm'),V(100,'inch')], unit = 'm')
        logging.debug(t._repr_html_())        
        
    def test003_m(self):
        v = V(60,'m/min')
        assert_equal(v('m/s'), 1)
        
    def test004_TableCell(self):
        t = Table('test cell',[],[])
        t.setCell(('speed','km/hour'),'car',V(100,'mph'))
        t.setCell('speed','bus',V(100,'km/hour'))
        assert_equal((t['speed']['car'])('km/hour'),160.93439999999998)
        t.setCell('acceleration','car',V(1,'m/s^2'))
        logging.info(t._repr_html_())
        
class TestMagnitudeIn:
    def test_magnitude_in(self):
        # assert_equal(expected, magnitudeIn(self, unit))
        raise SkipTest # TODO: implement your test here

class TestIsfunc:
    def test_isfunc(self):
        # assert_equal(expected, isfunc(self, col))
        raise SkipTest # TODO: implement your test here

class TestSetCell:
    def test_set_cell(self):
        # assert_equal(expected, setCell(self, row, col, value))
        raise SkipTest # TODO: implement your test here

class TestAppendCol:
    def test_append_col(self):
        # assert_equal(expected, appendCol(self, colname, values))
        raise SkipTest # TODO: implement your test here

class TestAppendRow:
    def test_append_row(self):
        # assert_equal(expected, appendRow(self, label, values, unit))
        raise SkipTest # TODO: implement your test here

class TestAppendColFromObj:
    def test_append_col_from_obj(self):
        # assert_equal(expected, appendColFromObj(self, colname, obj, default))
        raise SkipTest # TODO: implement your test here

if __name__ == "__main__":
    runmodule()