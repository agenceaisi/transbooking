"""Output serializers for the dashboard responses.

These serializers document the response shapes for the OpenAPI schema. The
dashboards are read-only aggregations built in ``services.py``; the views feed
the already-computed dicts/lists straight into these serializers.
"""
from rest_framework import serializers


# --------------------------------------------------------------------------- #
# Voyageur
# --------------------------------------------------------------------------- #
class TravelerNextTripSerializer(serializers.Serializer):
    ticket_number = serializers.CharField()
    origin = serializers.CharField()
    destination = serializers.CharField()
    departure_time = serializers.DateTimeField()
    seat_number = serializers.CharField()
    status = serializers.CharField()


class NotificationSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    is_read = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class TravelerDashboardSerializer(serializers.Serializer):
    next_trips = TravelerNextTripSerializer(many=True)
    active_bookings_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    recent_notifications = NotificationSummarySerializer(many=True)


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class AgentDepartureSerializer(serializers.Serializer):
    trip_id = serializers.IntegerField()
    origin = serializers.CharField()
    destination = serializers.CharField()
    departure_time = serializers.DateTimeField()
    available_seats = serializers.IntegerField()
    passenger_count = serializers.IntegerField()


class AgentDashboardSerializer(serializers.Serializer):
    next_departures = AgentDepartureSerializer(many=True)
    pending_alerts = serializers.IntegerField()
    connection_status = serializers.CharField()


# --------------------------------------------------------------------------- #
# Company admin
# --------------------------------------------------------------------------- #
class CompanyOverviewDeltaSerializer(serializers.Serializer):
    revenue_total = serializers.FloatField()
    fill_rate_avg = serializers.FloatField()
    bookings_count = serializers.IntegerField()


class CompanyOverviewSerializer(serializers.Serializer):
    period = serializers.CharField()
    revenue_total = serializers.FloatField()
    fill_rate_avg = serializers.FloatField()
    bookings_count = serializers.IntegerField()
    avg_rating = serializers.FloatField(allow_null=True)
    vs_previous_period = CompanyOverviewDeltaSerializer()


class RevenuePointSerializer(serializers.Serializer):
    date = serializers.DateField()
    revenue = serializers.FloatField()


class FillRateByRouteSerializer(serializers.Serializer):
    route_label = serializers.CharField()
    fill_rate_pct = serializers.FloatField()


class PaymentBreakdownSerializer(serializers.Serializer):
    method = serializers.CharField()
    amount = serializers.FloatField()
    pct = serializers.FloatField()


class TopRouteSerializer(serializers.Serializer):
    route = serializers.CharField()
    revenue = serializers.FloatField()
    passengers = serializers.IntegerField()


class AgentActivitySerializer(serializers.Serializer):
    agent_name = serializers.CharField()
    bookings_today = serializers.IntegerField()
    parcels_today = serializers.IntegerField()


class CompanyAlertsSerializer(serializers.Serializer):
    unresolved_claims = serializers.IntegerField()
    unreturned_parcels = serializers.IntegerField()
    speed_reports_pending = serializers.IntegerField()


# --------------------------------------------------------------------------- #
# Super admin
# --------------------------------------------------------------------------- #
class SuperOverviewSerializer(serializers.Serializer):
    total_companies = serializers.IntegerField()
    active_companies = serializers.IntegerField()
    total_bookings = serializers.IntegerField()
    total_commission_revenue = serializers.FloatField()
    active_users = serializers.IntegerField()


class RevenueByCompanySerializer(serializers.Serializer):
    company = serializers.CharField()
    revenue = serializers.FloatField()
    commission = serializers.FloatField()


class BookingsChartPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
