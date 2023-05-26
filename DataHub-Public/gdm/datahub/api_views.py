import re
from rest_framework import viewsets
from . import models
from . import serializers
from . import actions
from rest_framework import permissions
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .jobs import JobScheduler
import json


class DatasetViewset(viewsets.ModelViewSet):
    queryset = models.Dataset.objects.all()
    serializer_class = serializers.DatasetSerializer
    permission_classes = [permissions.IsAuthenticated]


class ReportViewset(viewsets.ModelViewSet):
    queryset = models.Report.objects.all()
    serializer_class = serializers.ReportSerializer
    permission_classes = [permissions.IsAuthenticated]


class OriginViewset(viewsets.ModelViewSet):
    queryset = models.Origin.objects.all()
    serializer_class = serializers.OriginSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserViewset(viewsets.ModelViewSet):
    queryset = models.User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated]

# @api_view(['POST'])
# def sambaexport(request):
#     serializer = serializers.DatasetSerializer(data=request.data)
#     permission_classes = [permissions.IsAuthenticated]
#     if serializer.is_valid():
#         serializer.save()
#         return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
#     else:
#         return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ODKImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):
        # queryset = models.Dataset.objects.all()
        serializer = serializers.ODKImportSerializer(data=kwargs)
        if serializer.is_valid():
            params = json.loads(kwargs['params'].replace("'",'"'))
            csv_type = 'attachment'
            scheduled = False # True # Do it now or later
            jobScheduler = JobScheduler(request.user,params,csv_type,scheduled)
            jobScheduler.start()
            # serializer.validated_data()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class SambaExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):        
        serializer = serializers.DatasetSerializer(data=kwargs)        
        if serializer.is_valid():
            id = json.loads(kwargs['id'].replace("'",'"'))
            dataset = models.Dataset.objects.get(pk=id)
            actions.export_dataset_samba(dataset)
            # serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class EasydbExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):        
        serializer = serializers.DatasetSerializer(data=kwargs)        
        if serializer.is_valid():
            id = json.loads(kwargs['id'].replace("'",'"'))
            dataset = models.Dataset.objects.get(pk=id)
            actions.export_dataset_easydb(dataset)
            # serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CSVExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):        
        serializer = serializers.DatasetSerializer(data=kwargs)        
        if serializer.is_valid():
            id = json.loads(kwargs['id'].replace("'",'"'))
            dataset = models.Dataset.objects.get(pk=id)
            actions.export_csv_specify(dataset)
            # serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class PicturaeExportView(APIView):
    def post(self, request, *args, **kwargs):    
        permission_classes = [permissions.IsAuthenticated, permissions.BasePermission.has_permission(self,request,PicturaeExportView)]    
        serializer = serializers.MassDigiSerializer(data=kwargs)        
        if serializer.is_valid():
            # id = json.loads(kwargs['id'].replace("'",'"'))
            # dataset = models.Dataset.objects.get(pk=id)
            actions.export_dataset_picturae(request)
            # serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
