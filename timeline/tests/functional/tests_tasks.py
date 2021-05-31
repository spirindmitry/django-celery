from unittest.mock import patch

from django.core import mail
from freezegun import freeze_time
from mixer.backend.django import mixer

from accounting.tasks import bill_timeline_entries
from elk.utils.testing import ClassIntegrationTestCase, create_customer
from market.models import Subscription
from products.models import Product1
from timeline.tasks import notify_15min_to_class, notify_1day_unused_lessons


class TestNotUsedSubscriptionEmail(ClassIntegrationTestCase):

    def setUp(self):
        super(TestNotUsedSubscriptionEmail, self).setUp()
        self.s = Subscription(
            customer=create_customer(),
            product=Product1.objects.get(pk=1),
            buy_price=150,

        )
        self.s.save()

        self.entry = self._create_entry()
        self.entry.is_finished = True
        self.entry.save()

    @patch('market.signals.Owl')
    def test_notify_email(self, Owl):

        c = self.s.classes.first()
        self._schedule(c, self.entry)

        with freeze_time('2032-09-21 15:46'):   # a week after the last lesson
            for i in range(0, 10):  # run this 10 times to check for repietive emails — all notifications should be sent one time
                notify_1day_unused_lessons()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.s.customer.user.email, mail.outbox[0].to[0])

    @patch('market.signals.Owl')
    def test_notify_email_not_send_if_a_week_has_not_passed(self, Owl):

        with freeze_time('2032-09-19 15:46'):  # less a week after the last lesson
            for i in range(0, 10):
                notify_1day_unused_lessons()

        self.assertEqual(len(mail.outbox), 0)

    @patch('market.signals.Owl')
    def test_notify_email_not_send_if_finished_entries_not_exist(self, Owl):
        self.entry.is_finished = False
        self.entry.save()

        with freeze_time('2032-09-21 15:46'):   # a week after the last lesson
            for i in range(0, 10):
                notify_1day_unused_lessons()

        self.assertEqual(len(mail.outbox), 0)

    @patch('market.signals.Owl')
    def test_notify_email_not_send_again(self, Owl):
        self.s.not_used_notifications_sent_to_customer = True
        self.s.save()

        with freeze_time('2032-09-21 15:46'):   # a week after the last lesson
            for i in range(0, 10):
                notify_1day_unused_lessons()

        self.assertEqual(len(mail.outbox), 0)

    @patch('market.signals.Owl')
    def test_notify_email_send_if_the_user_came_back_and_left_again(self, Owl):
        self.s.not_used_notifications_sent_to_customer = True
        self.s.save()

        with freeze_time('2032-09-16 15:46'):
            bill_timeline_entries()

        with freeze_time('2032-09-26 15:46'):   # a week after the last lesson
            for i in range(0, 10):
                notify_1day_unused_lessons()

        self.assertEqual(len(mail.outbox), 0)


class TestStartingSoonEmail(ClassIntegrationTestCase):
    @patch('market.signals.Owl')
    def test_single_class_pre_start_notification(self, Owl):
        entry = self._create_entry()
        c = self._buy_a_lesson()
        self._schedule(c, entry)

        with freeze_time('2032-09-13 15:46'):   # entry will start in 14 minutes
            for i in range(0, 10):  # run this 10 times to check for repietive emails — all notifications should be sent one time
                notify_15min_to_class()

        self.assertEqual(len(mail.outbox), 2)  # if this test fails, carefully check the timezone you are in

        out_emails = [outbox.to[0] for outbox in mail.outbox]

        self.assertIn(self.host.user.email, out_emails)
        self.assertIn(self.customer.user.email, out_emails)

    @patch('market.signals.Owl')
    def test_two_classes_pre_start_notification(self, Owl):
        self.lesson = mixer.blend('lessons.MasterClass', host=self.host, slots=5)

        other_customer = create_customer()
        first_customer = self.customer

        entry = self._create_entry()
        entry.slots = 5
        entry.save()

        c = self._buy_a_lesson()
        self._schedule(c, entry)

        self.customer = other_customer
        c1 = self._buy_a_lesson()
        self._schedule(c1, entry)
        with freeze_time('2032-09-13 15:46'):   # entry will start in 14 minutes
            for i in range(0, 10):  # run this 10 times to check for repietive emails — all notifications should be sent one time
                notify_15min_to_class()

        self.assertEqual(len(mail.outbox), 3)  # if this test fails, carefully check the timezone you are in

        out_emails = [outbox.to[0] for outbox in mail.outbox]

        self.assertIn(self.host.user.email, out_emails)
        self.assertIn(first_customer.user.email, out_emails)
        self.assertIn(other_customer.user.email, out_emails)
