import random
from datetime import datetime, timedelta
import pytest

from mock import Mock, patch

import factory
from factory import fuzzy
from django.utils.timezone import now
from django.db import transaction
from django.test import TestCase, Client
from django.conf import settings
from django.contrib.auth.models import Permission

from network.base.models import (ANTENNA_BANDS, ANTENNA_TYPES, RIG_TYPES, OBSERVATION_STATUSES,
                                 Rig, Mode, Antenna, Satellite, Tle, Station, Transmitter,
                                 Observation, Data, DemodData)
from network.users.tests import UserFactory


RIG_TYPE_IDS = [c[0] for c in RIG_TYPES]
ANTENNA_BAND_IDS = [c[0] for c in ANTENNA_BANDS]
ANTENNA_TYPE_IDS = [c[0] for c in ANTENNA_TYPES]
OBSERVATION_STATUS_IDS = [c[0] for c in OBSERVATION_STATUSES]


def generate_payload():
    payload = '{0:b}'.format(random.randint(500000000, 510000000))
    digits = 1824
    while digits:
        digit = random.randint(0, 1)
        payload += str(digit)
        digits -= 1
    return payload


def generate_payload_name():
    filename = datetime.strftime(fuzzy.FuzzyDateTime(now() - timedelta(days=10), now()).fuzz(),
                                 '%Y%m%dT%H%M%SZ')
    return filename


def get_valid_satellites():
    qs = Transmitter.objects.all()
    satellites = Satellite.objects.filter(transmitters__in=qs).distinct()
    return satellites


class RigFactory(factory.django.DjangoModelFactory):
    """Rig model factory."""
    name = fuzzy.FuzzyChoice(choices=RIG_TYPE_IDS)
    rictld_number = fuzzy.FuzzyInteger(1, 3)

    class Meta:
        model = Rig


class ModeFactory(factory.django.DjangoModelFactory):
    """Mode model factory."""
    name = fuzzy.FuzzyText()

    class Meta:
        model = Mode


class AntennaFactory(factory.django.DjangoModelFactory):
    """Antenna model factory."""
    frequency = fuzzy.FuzzyFloat(200, 500)
    band = fuzzy.FuzzyChoice(choices=ANTENNA_BAND_IDS)
    antenna_type = fuzzy.FuzzyChoice(choices=ANTENNA_TYPE_IDS)

    class Meta:
        model = Antenna


class StationFactory(factory.django.DjangoModelFactory):
    """Station model factory."""
    owner = factory.SubFactory(UserFactory)
    name = fuzzy.FuzzyText()
    image = factory.django.ImageField()
    alt = fuzzy.FuzzyInteger(0, 800)
    lat = fuzzy.FuzzyFloat(-20, 70)
    lng = fuzzy.FuzzyFloat(-180, 180)
    featured_date = fuzzy.FuzzyDateTime(now() - timedelta(days=10), now())
    active = fuzzy.FuzzyChoice(choices=[True, False])
    last_seen = fuzzy.FuzzyDateTime(now() - timedelta(days=3), now())
    horizon = fuzzy.FuzzyInteger(10, 20)
    rig = factory.SubFactory(RigFactory)

    @factory.post_generation
    def antennas(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for antenna in extracted:
                if random.randint(0, 1):
                    self.antenna.add(antenna)

    class Meta:
        model = Station


class SatelliteFactory(factory.django.DjangoModelFactory):
    """Sattelite model factory."""
    norad_cat_id = fuzzy.FuzzyInteger(2000, 4000)
    name = fuzzy.FuzzyText()

    class Meta:
        model = Satellite


class TleFactory(factory.django.DjangoModelFactory):
    """Tle model factory."""
    tle0 = '3CAT-2'
    tle1 = '1 40043U 14033AK  16355.56523826  .00000180  00000-0  34302-4 0  9994'
    tle2 = '2 40043  97.8794 239.3735 0060963 147.7144 212.7819 14.73885035134520'
    updated = fuzzy.FuzzyDateTime(now() - timedelta(days=3), now())
    satellite = factory.SubFactory(SatelliteFactory)

    class Meta:
        model = Tle


class TransmitterFactory(factory.django.DjangoModelFactory):
    """Transmitter model factory."""
    description = fuzzy.FuzzyText()
    alive = fuzzy.FuzzyChoice(choices=[True, False])
    uplink_low = fuzzy.FuzzyInteger(200000000, 500000000, step=10000)
    uplink_high = fuzzy.FuzzyInteger(200000000, 500000000, step=10000)
    downlink_low = fuzzy.FuzzyInteger(200000000, 500000000, step=10000)
    downlink_high = fuzzy.FuzzyInteger(200000000, 500000000, step=10000)
    mode = factory.SubFactory(ModeFactory)
    invert = fuzzy.FuzzyChoice(choices=[True, False])
    baud = fuzzy.FuzzyInteger(4000, 22000, step=1000)
    satellite = factory.SubFactory(SatelliteFactory)

    class Meta:
        model = Transmitter


class ObservationFactory(factory.django.DjangoModelFactory):
    """Observation model factory."""
    satellite = factory.Iterator(get_valid_satellites())
    author = factory.SubFactory(UserFactory)
    start = fuzzy.FuzzyDateTime(now() - timedelta(days=3),
                                now() + timedelta(days=3))
    end = factory.LazyAttribute(
        lambda x: x.start + timedelta(hours=random.randint(1, 8))
    )

    @factory.lazy_attribute
    def transmitter(self):
        return self.satellite.transmitters.all().order_by('?')[0]

    class Meta:
        model = Observation


class DataFactory(factory.django.DjangoModelFactory):
    start = fuzzy.FuzzyDateTime(now() - timedelta(days=3),
                                now() + timedelta(days=3))
    end = factory.LazyAttribute(
        lambda x: x.start + timedelta(minutes=random.randint(1, 20))
    )
    observation = factory.SubFactory(ObservationFactory)
    ground_station = factory.Iterator(Station.objects.all())
    payload = factory.django.FileField(filename='data.ogg')
    vetted_datetime = factory.LazyAttribute(
        lambda x: x.end + timedelta(hours=random.randint(1, 20))
    )
    vetted_user = factory.SubFactory(UserFactory)
    vetted_status = fuzzy.FuzzyChoice(choices=OBSERVATION_STATUS_IDS)

    class Meta:
        model = Data


class DemodDataFactory(factory.django.DjangoModelFactory):
    data = factory.Iterator(Data.objects.all())
    payload_demod = factory.django.FileField()

    class Meta:
        model = DemodData


@pytest.mark.django_db(transaction=True)
class HomeViewTest(TestCase):
    """
    Simple test to make sure the home page is working
    """
    def test_home_page(self):
        response = self.client.get('/')
        self.assertContains(response, 'Ground stations swarm control, at your fingertips.')


@pytest.mark.django_db(transaction=True)
class AboutViewTest(TestCase):
    """
    Simple test to make sure the about page is working
    """
    def test_about_page(self):
        response = self.client.get('/about/')
        self.assertContains(response, 'SatNOGS Network is a global management interface')


@pytest.mark.django_db
class SatellitePositionViewTest(TestCase):
    """
    Simple test to make sure this view returns a valid json
    """
    client = Client()

    satellites = []
    tles = []

    def setUp(self):
        for x in xrange(1, 10):
            self.tles.append(TleFactory())
        for x in xrange(1, 10):
            self.satellites = Satellite.objects.all()

    def test_satellite_position(self):
        for x in self.satellites:
            response = self.client.get('/satellite_position/{0}/'.format(x.norad_cat_id))
            response.json()['lat']
            response.json()['lon']


@pytest.mark.django_db
class StationListViewTest(TestCase):
    """
    Test to ensure the station list is generated by Django
    """
    client = Client()
    stations = []

    def setUp(self):
        for x in xrange(1, 10):
            self.stations.append(StationFactory())

    def test_station_list(self):
        response = self.client.get('/stations/')
        for x in self.stations:
            self.assertContains(response, x.owner)
            self.assertContains(response, x.name)


@pytest.mark.django_db(transaction=True)
class ObservationsListViewTest(TestCase):
    """
    Test to ensure the observation list is generated by Django
    """
    client = Client()
    observations = []
    satellites = []
    transmitters = []

    def setUp(self):
        # Clear the data and create some new random data
        with transaction.atomic():
            Observation.objects.all().delete()
            Transmitter.objects.all().delete()
            Satellite.objects.all().delete()
        self.satellites = []
        self.observations = []
        self.transmitters = []
        with transaction.atomic():
            for x in xrange(1, 10):
                self.satellites.append(SatelliteFactory())
            for x in xrange(1, 10):
                self.transmitters.append(TransmitterFactory(satellite=self.satellites[0]))
            for x in xrange(1, 10):
                self.observations.append(ObservationFactory(satellite=self.satellites[0]))

    def test_observations_list(self):
        response = self.client.get('/observations/')

        for x in self.observations:
            self.assertContains(response, x.transmitter.mode.name)

    def test_observations_list_deselect_bad(self):
        response = self.client.get('/observations/?bad=0')
        print response

        for x in self.observations:
            self.assertNotContains(response, x.transmitter.mode.name)

    def test_observations_list_deselect_good(self):
        response = self.client.get('/observations/?good=0')

        for x in self.observations:
            self.assertContains(response, x.transmitter.mode.name)

    def test_observations_list_deselect_unvetted(self):
        response = self.client.get('/observations/?unvetted=0')

        for x in self.observations:
            self.assertContains(response, x.transmitter.mode.name)


class NotFoundErrorTest(TestCase):
    """
    Test the 404 not found handler
    """
    client = Client()

    def test_404_not_found(self):
        response = self.client.get('/blah')
        self.assertEquals(response.status_code, 404)


class RobotsViewTest(TestCase):
    """
    Test the robots.txt handler
    """
    client = Client()

    def test_robots(self):
        response = self.client.get('/robots.txt')
        self.assertContains(response, 'Disallow: /')


@pytest.mark.django_db(transaction=True)
class ObservationViewTest(TestCase):
    """
    Test to ensure the observation list is generated by Django
    """
    client = Client()
    observation = None
    satellites = []
    transmitters = []
    user = None

    def setUp(self):
        self.user = UserFactory()
        self.user.user_permissions.add(
            Permission.objects.get(codename='delete_observation'))
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        self.observation = ObservationFactory()

    def test_observation(self):
        response = self.client.get('/observations/%d/' % self.observation.id)
        self.assertContains(response, self.observation.author.username)
        self.assertContains(response, self.observation.transmitter.mode.name)
        if not self.observation.is_deletable_before_start:
            self.assertNotContains(response, 'Delete Observation')

    def test_observation_staff(self):
        self.client.force_login(self.user)
        response = self.client.get('/observations/%d/' % self.observation.id)
        if self.observation.is_deletable_after_end:
            self.assertContains(response, 'Delete Observation')


@pytest.mark.django_db(transaction=True)
class ObservationDeleteTest(TestCase):
    """
    Test to ensure the observation list is generated by Django
    """
    client = Client()
    user = None
    observation = None
    satellites = []
    transmitters = []

    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        self.observation = ObservationFactory()
        self.observation.author = self.user
        # observations in progress cannot be deleted
        self.observation.start = datetime.now() + timedelta(
            minutes=(2 * int(settings.OBSERVATION_MAX_DELETION_RANGE)))
        self.observation.end = datetime.now() - timedelta(
            minutes=(2 * int(settings.OBSERVATION_MIN_DELETION_RANGE)))
        self.observation.save()

    def test_observation_delete_author(self):
        """Deletion OK when user is the author of the observation"""
        response = self.client.get('/observations/%d/delete/' % self.observation.id)
        self.assertRedirects(response, '/observations/')
        response = self.client.get('/observations/')
        with self.assertRaises(Observation.DoesNotExist):
            _lookup = Observation.objects.get(pk=self.observation.id)       # noqa:F841

    def test_observation_delete_staff(self):
        """Deletion OK when user is staff and there is no data"""
        self.user = UserFactory()
        self.user.user_permissions.add(
            Permission.objects.get(codename='delete_observation'))
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get('/observations/%d/delete/' % self.observation.id)
        self.assertRedirects(response, '/observations/')
        response = self.client.get('/observations/')
        with self.assertRaises(Observation.DoesNotExist):
            _lookup = Observation.objects.get(pk=self.observation.id)       # noqa:F841


@pytest.mark.django_db(transaction=True)
class StationViewTest(TestCase):
    """
    Test to ensure the observation list is generated by Django
    """
    client = Client()
    station = None

    def setUp(self):
        self.station = StationFactory()

    def test_observation(self):
        response = self.client.get('/stations/%d/' % self.station.id)
        self.assertContains(response, self.station.owner.username)
        self.assertContains(response, self.station.alt)
        self.assertContains(response, self.station.horizon)


@pytest.mark.django_db(transaction=True)
class StationDeleteTest(TestCase):
    """
    Test to ensure the observation list is generated by Django
    """
    client = Client()
    station = None
    user = None

    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.station = StationFactory()
        self.station.owner = self.user
        self.station.save()

    def test_station_delete(self):
        response = self.client.get('/stations/%d/delete/' % self.station.id)
        self.assertRedirects(response, '/users/%s/' % self.user.username)
        with self.assertRaises(Station.DoesNotExist):
            _lookup = Station.objects.get(pk=self.station.id)       # noqa:F841


@pytest.mark.django_db(transaction=True)
class SettingsSiteViewTest(TestCase):
    """
    Test to ensure the satellite fetch feature works
    """
    client = Client()
    user = None

    def setUp(self):
        self.user = UserFactory()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

    def test_get(self):
        response = self.client.get('/settings_site/')
        self.assertContains(response, 'Fetch Data')

    @patch('urllib2.urlopen', Mock())
    def test_post(self):
        response = self.client.post('/settings_site/', {'fetch': True})
        self.assertRedirects(response, '/settings_site/')


@pytest.mark.django_db(transaction=True)
class DataVerifyViewtest(TestCase):
    """
    Test marking data as vetted
    """
    client = Client()
    user = None
    data = None
    satellites = []
    stations = []
    transmitters = []
    observations = []

    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        for x in xrange(1, 10):
            self.observations.append(ObservationFactory())

        for x in xrange(1, 10):
            self.stations.append(StationFactory())

        self.data = DataFactory()

    def test_get_data_verify(self):
        response = self.client.get('/data_verify/%d/' % self.data.id)
        self.assertRedirects(response, '/observations/%d/' % self.data.observation.id)
        data = Data.objects.get(id=self.data.id)
        self.assertEqual(data.vetted_user.username, self.user.username)
        self.assertEqual(data.vetted_status, 'verified')


@pytest.mark.django_db(transaction=True)
class DataMarkBadViewtest(TestCase):
    """
    Test marking data as vetted
    """
    client = Client()
    user = None
    data = None
    satellites = []
    stations = []
    transmitters = []

    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        for x in xrange(1, 10):
            self.stations.append(StationFactory())

        self.data = DataFactory()

    def test_get_data_mark_bad(self):
        response = self.client.get('/data_mark_bad/%d/' % self.data.id)
        self.assertRedirects(response, '/observations/%d/' % self.data.observation.id)
        data = Data.objects.get(id=self.data.id)
        self.assertEqual(data.vetted_user.username, self.user.username)
        self.assertEqual(data.vetted_status, 'no_data')


@pytest.mark.django_db(transaction=True)
class SatelliteModelTest(TestCase):
    """
    Tests various methods of the Satellite model
    """
    satellite = None

    def setUp(self):
        self.satellite = SatelliteFactory()

    def test_latest_tle(self):
        self.assertFalse(self.satellite.latest_tle)

    def test_tle_epoch(self):
        self.assertFalse(self.satellite.tle_epoch)

    def test_tle_no(self):
        self.assertFalse(self.satellite.tle_no)


@pytest.mark.django_db(transaction=True)
class ObservationModelTest(TestCase):
    """
    Test various properties of the Observation Model
    """
    observation = None
    satellites = []
    transmitters = []
    user = None
    admin = None

    def setUp(self):
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        self.observation = ObservationFactory()
        self.observation.end = now()
        self.observation.save()

    def test_has_submitted_data(self):
        self.assertEqual(0, self.observation.has_submitted_data)

    def test_is_passed(self):
        self.assertTrue(self.observation.is_past)

    def test_is_deletable_before_start(self):
        self.observation.start = now() - timedelta(minutes=2)
        self.observation.save()
        self.assertFalse(self.observation.is_deletable_before_start)
        self.observation.start = now() + timedelta(minutes=100)
        self.observation.save()
        self.assertTrue(self.observation.is_deletable_before_start)

    def test_is_deletable_after_end(self):
        self.observation.end = now()
        self.observation.save()
        self.assertFalse(self.observation.is_deletable_after_end)
        self.observation.end = now() - timedelta(minutes=200)
        self.observation.save()
        self.assertTrue(self.observation.is_deletable_after_end)


@pytest.mark.django_db(transaction=True)
class DataModelTest(TestCase):
    """
    Test various properties of the Observation Model
    """
    data = None
    data2 = None
    satellites = []
    transmitters = []

    def setUp(self):
        for x in xrange(1, 10):
            self.satellites.append(SatelliteFactory())
        for x in xrange(1, 10):
            self.transmitters.append(TransmitterFactory())
        self.data = DataFactory()
        self.data.end = now()
        self.data.vetted_status = 'no_data'
        self.data.save()
        self.data2 = DataFactory(payload=None)

    def test_is_no_data(self):
        self.assertTrue(self.data.is_no_data)

    def test_is_passed(self):
        self.assertTrue(self.data.is_past)

    def test_payload_exists(self):
        self.assertFalse(self.data.payload_exists)
