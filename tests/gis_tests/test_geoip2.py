# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import unittest
from unittest import skipUnless

from django.conf import settings
from django.contrib.gis.geoip2 import HAS_GEOIP2
from django.contrib.gis.geos import HAS_GEOS, GEOSGeometry
from django.utils import six

if HAS_GEOIP2:
    from django.contrib.gis.geoip2 import GeoIP2, GeoIP2Exception


# Note: Requires both the GeoIP country and city datasets.
# The GEOIP_DATA path should be the only setting set (the directory
# should contain links or the actual database files 'GeoLite2-City.mmdb' and
# 'GeoLite2-City.mmdb'.
@skipUnless(HAS_GEOIP2 and getattr(settings, "GEOIP_PATH", None),
    "GeoIP is required along with the GEOIP_PATH setting.")
class GeoIPTest(unittest.TestCase):
    addr = '128.249.1.1'
    fqdn = 'tmc.edu'

    def test01_init(self):
        "GeoIP initialization."
        g1 = GeoIP2()  # Everything inferred from GeoIP path
        path = settings.GEOIP_PATH
        g2 = GeoIP2(path, 0)  # Passing in data path explicitly.
        g3 = GeoIP2.open(path, 0)  # MaxMind Python API syntax.

        for g in (g1, g2, g3):
            self.assertTrue(g._country)
            self.assertTrue(g._city)

        # Only passing in the location of one database.
        city = os.path.join(path, 'GeoLite2-City.mmdb')
        cntry = os.path.join(path, 'GeoLite2-Country.mmdb')
        g4 = GeoIP2(city, country='')
        self.assertIsNone(g4._country)
        g5 = GeoIP2(cntry, city='')
        self.assertIsNone(g5._city)

        # Improper parameters.
        bad_params = (23, 'foo', 15.23)
        for bad in bad_params:
            self.assertRaises(GeoIP2Exception, GeoIP2, cache=bad)
            if isinstance(bad, six.string_types):
                e = GeoIP2Exception
            else:
                e = TypeError
            self.assertRaises(e, GeoIP2, bad, 0)

    def test02_bad_query(self):
        "GeoIP query parameter checking."
        cntry_g = GeoIP2(city='<foo>')
        # No city database available, these calls should fail.
        self.assertRaises(GeoIP2Exception, cntry_g.city, 'tmc.edu')
        self.assertRaises(GeoIP2Exception, cntry_g.coords, 'tmc.edu')

        # Non-string query should raise TypeError
        self.assertRaises(TypeError, cntry_g.country_code, 17)
        self.assertRaises(TypeError, cntry_g.country_name, GeoIP2)

    def test03_country(self):
        "GeoIP country querying methods."
        g = GeoIP2(city='<foo>')

        for query in (self.fqdn, self.addr):
            self.assertEqual(
                'US',
                g.country_code(query),
                'Failed for func country_code and query %s' % query
            )
            self.assertEqual(
                'United States',
                g.country_name(query),
                'Failed for func country_name and query %s' % query
            )
            self.assertEqual(
                {'country_code': 'US', 'country_name': 'United States'},
                g.country(query)
            )

    @skipUnless(HAS_GEOS, "Geos is required")
    def test04_city(self):
        "GeoIP city querying methods."
        g = GeoIP2(country='<foo>')

        for query in (self.fqdn, self.addr):
            # Country queries should still work.
            self.assertEqual(
                'US',
                g.country_code(query),
                'Failed for func country_code and query %s' % query
            )
            self.assertEqual(
                'United States',
                g.country_name(query),
                'Failed for func country_name and query %s' % query
            )
            self.assertEqual(
                {'country_code': 'US', 'country_name': 'United States'},
                g.country(query)
            )

            # City information dictionary.
            d = g.city(query)
            self.assertEqual('US', d['country_code'])
            self.assertEqual('Houston', d['city'])
            self.assertEqual('TX', d['region'])

            geom = g.geos(query)
            self.assertIsInstance(geom, GEOSGeometry)
            lon, lat = (-95.4010, 29.7079)
            lat_lon = g.lat_lon(query)
            lat_lon = (lat_lon[1], lat_lon[0])
            for tup in (geom.tuple, g.coords(query), g.lon_lat(query), lat_lon):
                self.assertAlmostEqual(lon, tup[0], 4)
                self.assertAlmostEqual(lat, tup[1], 4)

    def test05_unicode_response(self):
        "GeoIP strings should be properly encoded (#16553)."
        g = GeoIP2()
        d = g.city("duesseldorf.de")
        self.assertEqual('Düsseldorf', d['city'])
        d = g.country('200.26.205.1')
        # Some databases have only unaccented countries
        self.assertIn(d['country_name'], ('Curaçao', 'Curacao'))

    def test06_ipv6_query(self):
        "GeoIP can lookup IPv6 addresses."
        g = GeoIP2()
        d = g.city('2002:81ed:c9a5::81ed:c9a5')  # IPv6 address for www.nhm.ku.edu
        self.assertEqual('US', d['country_code'])
        self.assertEqual('Lawrence', d['city'])
        self.assertEqual('KS', d['region'])
