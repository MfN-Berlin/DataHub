from dataclasses import fields
from rest_framework_json_api import serializers
from .models import Dataset, Report, Origin
from django.contrib.auth.models import User

# CRUD Serializers for core models
class DatasetSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Dataset
        fields = ['datetime', 'CSV', 'files', 'origin_id', 'params', 'flag']

class ReportSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model =  Report
        fields  = ['user', 'dataset', 'report_type', 'datetime', 'flag', 'comment']

class OriginSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model =  Origin
        fields  = ['title']

class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'groups']

# Functional Serializers
class ODKImportSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Dataset
        fields = ['params']

# Functional Serializers
class MassDigiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Dataset
        fields = ['params']
