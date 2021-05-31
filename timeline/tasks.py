from datetime import timedelta

from django.db.models import Max
from django.utils.timezone import now

from elk.celery import app as celery
from market.models import Class, Subscription
from timeline.signals import class_starting_student, class_starting_teacher, subscription_is_not_used


@celery.task
def notify_15min_to_class():
    for i in Class.objects.starting_soon(timedelta(minutes=30)).filter(pre_start_notifications_sent_to_teacher=False).distinct('timeline'):
        for other_class_with_the_same_timeline in Class.objects.starting_soon(timedelta(minutes=30)).filter(timeline=i.timeline):
            """
            Set all other starting classes as notified either.
            """
            other_class_with_the_same_timeline.pre_start_notifications_sent_to_teacher = True
            other_class_with_the_same_timeline.save()
        class_starting_teacher.send(sender=notify_15min_to_class, instance=i)

    for i in Class.objects.starting_soon(timedelta(minutes=30)).filter(pre_start_notifications_sent_to_student=False):
        i.pre_start_notifications_sent_to_student = True
        i.save()
        class_starting_student.send(sender=notify_15min_to_class, instance=i)


@celery.task
def notify_1day_unused_lessons():
    subscriptions_with_last_lessons = Subscription.objects.annotate(last_lesson_time=Max('classes__timeline__end'))

    for s in subscriptions_with_last_lessons.filter(is_fully_used=False,
                                                    not_used_notifications_sent_to_customer=False,
                                                    classes__timeline__is_finished=True,
                                                    last_lesson_time__lte=now() - timedelta(weeks=1)):
        s.not_used_notifications_sent_to_customer = True
        s.save()
        subscription_is_not_used.send(sender=notify_1day_unused_lessons, instance=s)
