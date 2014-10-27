from rest_framework import generics, status, viewsets, mixins, parsers, renderers, status, generics
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.authentication import get_authorization_header
from rest_framework.response import Response
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from social.apps.django_app.utils import psa
from be_local_server import serializers
from be_local_server.models import *
from geopy.distance import vincenty
from operator import itemgetter, attrgetter, methodcaller

import datetime
from django.forms.models import model_to_dict

import json

def getDistanceFromUser(user_lat, user_lng, item_lat, item_lng):
    user = (user_lat, user_lng)
    item = (item_lat, item_lng)

    return vincenty(user, item).miles

class ObtainAuthToken(APIView):
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = AuthTokenSerializer
    model = Token
    vendors_per_page = 20; 
 
    def post(self, request, backend):
        serializer = self.serializer_class(data=request.DATA)
        if backend == 'auth':
            if serializer.is_valid():
                token, created = Token.objects.get_or_create(user=serializer.object['user'])
                return Response({'token': token.key})
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        else:
            user = register_by_access_token(request, backend)
 
            if user and user.is_active:
                token, created = Token.objects.get_or_create(user=user)
                response = {}
                if user.is_staff:
                    vendor = Vendor.objects.get(user=user)
                    response = {'id': user.id, 'name': user.username, 'email' : user.email, 'first_name': user.first_name, 'last_name': user.last_name, 'userType': 'VEN', 'vendor' : serializers.VendorSerializer(vendor).data, 'token': token.key}
                else:
                    response = {'id': user.id, 'name': user.username, 'email' : user.email, 'first_name': user.first_name, 'last_name': user.last_name, 'userType': 'CUS', 'token': token.key}
                return Response(response)

@psa()
def register_by_access_token(request, backend):
    backend = request.backend
    # Split by spaces and get the array
    auth = get_authorization_header(request).split()
 
    if not auth or auth[0].lower() != 'token':
        msg = 'No token header provided.'
        return msg
 
    if len(auth) == 1:
        msg = 'Invalid token header. No credentials provided.'
        return msg
 
    access_token = auth[1]
 
    user = backend.do_auth(access_token)

    return user

class VendorDetailsView(generics.CreateAPIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        vendor = Vendor.objects.get(pk=request.DATA["id"])
        locations = SellerLocation.objects.filter(vendor=vendor)
        products = Product.objects.filter(vendor=vendor, stock="IS")

        return Response({"vendor":serializers.VendorSerializer(vendor).data, "locations":serializers.SellerLocationSerializer(locations, many=True).data, "products":serializers.ProductSerializer(products, many=True).data}, status=status.HTTP_200_OK)  


class AddVendorView(generics.CreateAPIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = serializers.VendorSerializer(data=request.DATA)

        if serializer.is_valid():
            user = User.objects.get(id=serializer.init_data['user'])
            user.is_staff = 1 # make the user a vendor
            user.save()

            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)   
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

class RWDVendorView(generics.RetrieveUpdateDestroyAPIView):
    """
    This view  provides an endpoint for Sellers to view and
    modify their information
    """
    
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.VendorSerializer

    def get(self, request):
        vendor = Vendor.objects.get(user=request.user)
        
        if vendor is not None:
            serializer = serializers.VendorSerializer(vendor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    #Do we want to have a vendor delete here?
    def delete(self, request):
        vendor = Vendor.objects.get(user=request.user)

        if vendor is not None:
            user = User.objects.get(id=serializer.init_data['user'])
            user.is_staff = 0
            user.save()
            vendor.delete()
            return Response("Success", status=status.HTTP_204_NO_CONTENT)
        else:
            return Response("Vendor not found", status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        vendor = Vendor.objects.get(user=request.user) 
   
        if vendor is not None:
            serializer = serializers.EditVendorSerializer(vendor, data=request.DATA, partial=True)
           
            if serializer.is_valid():
                serializer.save()

                d = serializer.data
                p = VendorPhoto.objects.get(pk=serializer.data["photo"])
                serializer.data["photo"] = serializers.VendorPhotoPathSerializer(p).data

                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
        else:
            return Response("Vendor not found", status=status.HTTP_404_NOT_FOUND) 

    def get_object(self):
        try:
            vendor = Vendor.objects.get(user=self.request.user)
        except vendor.DoesNotExist:
            raise Http404
        return vendor

class AddProductView(generics.CreateAPIView):
    """
    This view provides an endpoint for sellers to
    add a product to their products list.
    """         
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)     

    def post(self, request, *args, **kwargs):
        vendor = Vendor.objects.get(user=request.user)
        request.DATA['vendor'] = vendor.id
        
        serializer = serializers.AddProductSerializer(data=request.DATA, partial=True)

        if serializer.is_valid():
            current_product = serializer.save()

            return Response(status=status.HTTP_201_CREATED)

        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

class RWDProductView(generics.RetrieveUpdateDestroyAPIView):
    """
    This view provides an endpoint for sellers to
    read-write-delete a product from their products list.
    """   
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,) 
    serializer_class = serializers.ProductSerializer
    
    def get(self, request, product_id):       
        product = Product.objects.get(pk=product_id)
        
        if product is not None:
            serializer = serializers.ProductSerializer(product) 
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response("Product not found", status=status.HTTP_404_NOT_FOUND)  
    
    def delete(self, request, product_id):       
        product = Product.objects.get(pk=product_id)
        
        if product is not None:
            product.delete() 
            return Response("Success", status=status.HTTP_204_NO_CONTENT)
        else:
            return Response("Product not found", status=status.HTTP_404_NOT_FOUND)                  
    
    def patch(self, request, product_id):         
        product = Product.objects.get(pk=product_id) 
   
        if product is not None:
            serializer = serializers.AddProductSerializer(product, data=request.DATA, partial=True)
           
            if serializer.is_valid():
                serializer.save()

                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
        else:
            return Response("Product not found", status=status.HTTP_404_NOT_FOUND) 

class RWDSellerLocationView(generics.RetrieveUpdateAPIView):
    """
    This view provides an endpoint for deleting and modifying views         
    """
    permission_classes = (AllowAny,)
    serializer_class = serializers.SellerLocationSerializer

    def patch(self, request, location_id):

        # Workaround for a Django bug that doesn't allow for multiple nested objects to be deserialized properly
        # As a result, we need to clear out the hours for recurring events and re-add them each time
        if(request.method == 'PATCH'):
            location = SellerLocation.objects.get(pk=location_id)
            address = location.address
            address.date = None
            address.save()
            hours = OpeningHours.objects.filter(address=address)
            for hour in hours:
                hour.delete()

        self.id = location_id
        return self.partial_update(request)

    def get_object(self):
        try:
            location = SellerLocation.objects.get(pk = self.id)  
        except location.DoesNotExist:
            raise Http404
        return location

class DeleteSellerLocationView(generics.CreateAPIView):
    def post(self, request):
        if("id" in request.DATA.keys() and "action" in request.DATA.keys()):
            if(request.DATA["action"] == "restore"):
                location = SellerLocation.trash.get(pk=request.DATA["id"])

                if location is not None:
                    location.restore()
                    return Response("Restored location", status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response("Location not found for restore", status=status.HTTP_400_BAD_REQUEST)                    
            elif(request.DATA["action"] == "trash"):
                location = SellerLocation.objects.get(pk=request.DATA["id"])

                if location is not None:
                    location.delete()
                    return Response("Trashed location", status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response("Location not found for trashing", status=status.HTTP_400_BAD_REQUEST) 
        else:
            return Response("id not provided", status=status.HTTP_400_BAD_REQUEST)

class DeleteProductView(generics.CreateAPIView):
    def post(self, request):
        if("id" in request.DATA.keys() and "action" in request.DATA.keys()):
            if(request.DATA["action"] == "restore"):
                product = Product.trash.get(pk=request.DATA["id"])

                if product is not None:
                    product.restore()
                    return Response("Restored product", status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response("Product not found for restore", status=status.HTTP_400_BAD_REQUEST)                    
            elif(request.DATA["action"] == "trash"):
                product = Product.objects.get(pk=request.DATA["id"])

                if product is not None:
                    product.delete()
                    return Response("Trashed product", status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response("Product not found for trashing", status=status.HTTP_400_BAD_REQUEST) 
        else:
            return Response("id not provided", status=status.HTTP_400_BAD_REQUEST)               

class AddProductPhotoView(generics.CreateAPIView):
    """
    This view provides an endpoint to save product photo. 
    """
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,) 
    serializer_class = serializers.ProductPhotoSerializer
    model = ProductPhoto

class AddVendorPhotoView(generics.CreateAPIView):
    """
    This view provides an endpoint to save vendor photo.
    """
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,) 
    serializer_class = serializers.VendorPhotoSerializer
    model = VendorPhoto
    
class RWDProductPhotoView(generics.RetrieveUpdateDestroyAPIView):
    """
    This view provides an endpoint for sellers to
    read-write-delete a product's image.
    """  
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    
    serializer_class = serializers.ProductPhotoSerializer
    model = ProductPhoto  
            
class VendorProductView(generics.ListAPIView):
    """
    This view provides an endpoint for vendors to view their products.
    """   
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ProductSerializer

    def get_queryset(self):
        vendor = Vendor.objects.get(user=self.request.user)
        products = Product.objects.filter(vendor=vendor)

        if products is not None:
            return products
        else:
            return Response(status=status.HTTP_404_NOT_FOUND) 

class UpdateStockView(generics.CreateAPIView):
    """
    This view provides an endpoint for vendors to view their products.
    """   
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ProductSerializer

    def post(self, request):
        error = '{"error":"Required attributes not provided"}'
        if "product_id" in request.DATA and "value" in request.DATA:
            product = Product.objects.get(pk=request.DATA["product_id"])
            error = '{"error":"Provided data is invalid"}'
            if(product != None):
                if(request.DATA["value"] == "IS"):
                    product.stock = Product.IN_STOCK
                elif(request.DATA["value"] == "OOS"):
                    product.stock = Product.OUT_OF_STOCK
                product.save()
                return Response(status=status.HTTP_200_OK)            
        return Response(data=error, status=status.HTTP_400_BAD_REQUEST)

#TODO: Currenty this view simply returns all products rather
# than trending ones
class TrendingProductView(generics.ListAPIView):
    """
    This view provides an endpoint for customers to
    view currently trending products.
    """   
    permission_classes = (AllowAny,)
    serializer_class = serializers.ProductDisplaySerializer

    def post(self, request):
        if (request.DATA['user_position'] is not None):
            lat, lng = map(float, request.DATA['user_position'].strip('()').split(','))
            print "Sorting vendors by proximity to (" +str(lat)+","+str(lng)+")"

            locations = SellerLocation.objects.all()

            for location in locations: 
                location.sortkey = getDistanceFromUser(lat, lng, location.address.latitude, location.address.longitude)

            locations = sorted(locations, key=attrgetter('sortkey'))

            products = []
            vendors = [] 

            #Go through all locations sorted by proximity
            for location in locations:
                if(location.vendor not in vendors): #To make sure we don't add the same item from two diff. locations
                    vendors.append(location.vendor)
                    products.extend(Product.objects.filter(vendor=location.vendor, stock=Product.IN_STOCK))
            
            serializer = serializers.ProductDisplaySerializer(products, many=True) 
            return Response(serializer.data)

        else:
            products = Product.objects.filter(stock=Product.IN_STOCK)
            serializer = serializers.ProductDisplaySerializer(products)
            return response(serializer.data)  


class ListMarketsView(generics.ListAPIView):
    """
    this view provides an endpoint for customers to 
    view current markets
    """
    permission_classes = (AllowAny,)
    serializer_class = serializers.MarketDisplaySerializer

    def get_queryset(self):
        return Market.objects.all()


class MarketView(generics.ListAPIView):
    """
    This view provides an endpoint for customers to check the available 
    Seller locations for the given market id
    """

    permission_classes = (AllowAny,)
    serializer_class = serializers.AddSellerLocationSerializer

    def get_queryset(self):
        market_id = self.kwargs['market_id']
        market_address = Address.objects.get(pk=market_id)

        return SellerLocation.objects.filter(address = market_address)



class VendorsView(generics.ListAPIView):
    """
    This view provides an endpoint for customers to view
    vendors.
    """
    permission_classes = (AllowAny,)
    serializer_class = serializers.CustomerVendorSerializer

    def post(self, request):
        if (request.DATA['user_position'] is not None):

            lat, lng = map(float, request.DATA['user_position'].strip('()').split(','))

            locations = SellerLocation.objects.all()

            #Sort locations based on proximity to current user
            for location in locations: 
                location.sortkey = getDistanceFromUser(lat, lng, location.address.latitude, location.address.longitude)
                print "distance from user: " + str(location.sortkey); 

            locations = sorted(locations, key=attrgetter('sortkey'))

            vendors = []

            #Fill vendor queryset with order based on their closest locations
            for location in locations: 
                if(location.vendor not in vendors):
                    vendors.append(location.vendor)

            serializer = serializers.VendorSerializer(vendors, many=True)
            return Response(serializer.data)

        else: 
            vendors = Vendor.objects.all()
            serializer = serializers.VendorSerializer(vendors, many=True)
            return Response(serializer.data)

# class VendorsView(generics.ListAPIView):
#     """
#     This view provides an endpoint for customers to view
#     vendors.
#     """
#     permission_classes = (AllowAny,)

#     serializer_class = serializers.CustomerVendorSerializer

#     def date_handler(obj):
#         return obj.isoforma() if hasattrb(obj, 'isoformat') else obj

#     def post(self, request):

#         #Testing
#         print request.DATA['test']

#         data = Vendor.objects.all()

#         dictionaries = [obj.as_dict() for obj in data]

#         for item in dictionaries:
#             item['user'] = model_to_dict(item['user'])
#             item['photo'] = model_to_dict(item['photo'])
#             item['address'] = model_to_dict(item['address'])

#         dthandler = lambda obj: (
#             obj.isoformat()
#             if isinstance(obj, datetime.datetime)
#             or isinstance(obj, datetime.date)
#             else None)

#         return HttpResponse(json.dumps(dictionaries, default=dthandler), content_type='application/json')

class ListVendorLocations(generics.ListAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = serializers.SellerLocationSerializer

    def get_queryset(self):
        vendor = Vendor.objects.get(user=self.request.user)

        return SellerLocation.objects.filter(vendor=vendor)

class AddSellerLocationView(generics.CreateAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        vendor = Vendor.objects.get(user=request.user)
        request.DATA['vendor'] = vendor.id       

        serializer = serializers.SellerLocationSerializer(data=request.DATA, many=False)

        if serializer.is_valid(): 
            current_location = serializer.save()
            address = current_location.address.id;             

            return HttpResponse(status=status.HTTP_201_CREATED)

        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)  

