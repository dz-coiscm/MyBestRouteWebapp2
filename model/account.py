import webapp2
import logging, json
import time, datetime
import config

from google.appengine.ext import ndb
from google.appengine.api import channel
import webapp2_extras.appengine.auth.models
from webapp2_extras import security

from base_model import BaseModel, UserTimeZone
from config import DEBUG
from utils.exception_utils import * 



'''
class for Price Plan
the plan name is the id which should be unique
'''
class PricePlan(BaseModel):
    
    #Plan name must be unique
    plan_name = ndb.StringProperty(required=True)
    #Private plan is only available to a particular 
    #plan_type = ndb.StringProperty(required=True, choices=['Public', 'Private'])
    plan_price = ndb.FloatProperty(required=True, default=0.0)
    description = ndb.StringProperty(indexed=False)
    
    #Modules that allowed to be used in the plan
    plan_modules = ndb.StringProperty(repeated=True, 
                                      choices=['Booking', 'Planning', 'Tracking'], 
                                      verbose_name='Booking,Planning,Tracking')
    
    #max_user_per_group = ndb.IntegerProperty(required=True, indexed=False)
    #max_route_per_group =ndb.IntegerProperty(required=True, indexed=False)
    #max_loc_per_route = ndb.IntegerProperty(required=True, indexed=False)
    plan_created = ndb.DateTimeProperty(auto_now_add=True)
    plan_updated = ndb.DateTimeProperty(auto_now=True)
    
    model_display_name = 'price plan'
    unique_or_props = ['plan_name'] 
    
    
    '''@classmethod
    def query_all(cls):
        return cls.query().order(cls.plan_type, cls.plan_price)
    '''
    
    @classmethod
    def prepare_query_order(cls, order_list):
        if order_list == None:
            order_list = [cls.plan_name, cls.plan_price]
        return order_list
    
    @classmethod
    def prepare_check_key(cls):
        check_existing_key = []
        
        new_check_key = {}
        new_check_key['model_display_name'] = 'business group'
        new_check_key['model_cls'] = BusinessGroup
        new_check_key['other_prop'] = BusinessGroup.price_plan
        check_existing_key.append(new_check_key)
        return check_existing_key       
'''
class for Account (business or personal)
a numeric key id will be generated for the account
'''
class BusinessGroup(BaseModel):
    business_name = ndb.StringProperty(required=True)
    price_plan = ndb.KeyProperty(required=True, kind=PricePlan, verbose_name='plan_name')
    status = ndb.StringProperty(required=True, 
                                default=config.PENDING_STATUS, 
                                choices=config.ACCOUNT_STATUS,
                                verbose_name=','.join(config.ACCOUNT_STATUS))
    country = ndb.StringProperty(required=True,
                                 default='Singapore',
                                 choices = config.COUNTRY_LIST, 
                                 verbose_name=','.join(config.COUNTRY_LIST))
    timezone = ndb.StringProperty(required=True, verbose_name="timezone_option")
    expiry_date = ndb.DateProperty()
    paypal_id = ndb.StringProperty(indexed=False)    
    last_payment = ndb.DateProperty(indexed=False)

    unique_or_props = ['business_name']
    model_display_name = 'business group'
    
    @classmethod
    def prepare_query_order(cls, order_list):
        if order_list == None:
            order_list = [-cls.tm_created, cls.price_plan, cls.business_name]
        return order_list

    @classmethod
    def prepare_check_key(cls):
        check_existing_key = []
        
        new_check_key = {}
        new_check_key['model_display_name'] = 'user'
        new_check_key['model_cls'] = User
        new_check_key['other_prop'] = User.business_group
        check_existing_key.append(new_check_key)

        new_check_key = {}
        new_check_key['model_display_name'] = 'business team'
        new_check_key['model_cls'] = BusinessTeam
        new_check_key['other_prop'] = BusinessTeam.business_group
        check_existing_key.append(new_check_key)
        
        return check_existing_key

'''
class for UserRole
For security control
'''
class UserRole(BaseModel):
    role_name = ndb.StringProperty(required=True)
    access_level = ndb.IntegerProperty(required=True, default=1)
    description = ndb.TextProperty(indexed=False)
    unique_or_props = ['role_name']   
    model_display_name = 'user role'
    
    '''
    @classmethod
    def query_all(cls):
        return cls.query().order(-cls.access_level)
    '''
    @classmethod
    def prepare_query_order(cls, order_list):
        if order_list == None:
            order_list = [-cls.access_level]        
        return order_list

    @classmethod
    def prepare_check_key(cls):
        check_existing_key = []
        
        new_check_key = {}
        new_check_key['model_display_name'] = 'user'
        new_check_key['model_cls'] = User
        new_check_key['other_prop'] = User.user_role
        check_existing_key.append(new_check_key)
        return check_existing_key

class BusinessTeam(BaseModel):
    team_name = ndb.StringProperty(required=True)
    team_description = ndb.TextProperty()
    business_group = ndb.KeyProperty(required=True,kind=BusinessGroup, verbose_name='business_name')
    country = ndb.StringProperty(required=True,
                                 default=lambda self: self.business_group.get().country,
                                 choices = config.COUNTRY_LIST, 
                                 verbose_name=','.join(config.COUNTRY_LIST))
    timezone = ndb.StringProperty(required=True, verbose_name="timezone_option")
    tracking_report_emails = ndb.StringProperty(repeated=True)
    status = ndb.StringProperty(required=True, 
                                default=config.ACTIVE_STATUS, 
                                choices=config.TEAM_STATUS,
                                verbose_name=','.join(config.TEAM_STATUS))
        
    unique_level = config.GROUP_UNIQUE.unique_level    
    unique_and_props = ['team_name']
    model_display_name = 'business team'   

    @classmethod
    def prepare_check_key(cls):
        check_existing_key = []
        
        new_check_key = {}
        new_check_key['model_display_name'] = 'user'
        new_check_key['model_cls'] = User
        new_check_key['other_prop'] = User.business_team
        check_existing_key.append(new_check_key)

        return check_existing_key
    
    @classmethod
    def get_prop_id_list(cls, prop_name, 
                         cur_user=None,
                         cond_list=None):
        cond_list=[cls.status==config.ACTIVE_STATUS]
        return super(BusinessTeam,cls).get_prop_id_list(prop_name=prop_name,
                                                       cur_user=cur_user,
                                                       cond_list=cond_list)

    
class ChannelMessage(object):
    def __init__(self, 
                 message,
                 cur_user,
                 message_type = None,
                 received_users = None,
                 received_groups = None,
                 received_teams = None,
                 received_pages = None,
                 
                 ):
        self.message = message
        self.message_type = message_type
        self.received_users = self.entity_list_to_dict(received_users, cur_user)
        self.received_groups = self.entity_list_to_dict(received_groups, cur_user)
        self.received_teams = self.entity_list_to_dict(received_teams, cur_user)
        self.received_pages = received_pages
    
    @staticmethod            
    def entity_list_to_dict(entity_list, cur_user):
        result_list = None
        if entity_list == None or len(entity_list) == 0:
            result_list = None
        else:
            result_list = []
            for each in entity_list:
                entity_id = each.to_dict(cur_user)['_entity_id']
                result_list.append(entity_id)
        return result_list
    
    def send(self, received_user):
        client_id = received_user.email_lower
        message = json.dumps(self.__dict__)
        channel.send_message(client_id, message)
        
    def broadcast(self):
        logging.info("broadcasting")
        all_channels = UserChannel.get_valid_channels()
        message = json.dumps(self.__dict__)
        for each in all_channels:
            client_id = each.email_lower
            channel.send_message(client_id, message)
    
class UserChannel(BaseModel):
    email_lower = ndb.StringProperty(required=True)
    token = ndb.StringProperty(required=True)
    expired = ndb.DateTimeProperty(required=True)
    
    @classmethod
    def query_user_channel(cls, email_lower):
        query_result = cls.query(cls.email_lower == email_lower)
        return query_result.get()
    
    @classmethod
    def create_user_channel(cls, email_lower):
        user_channel = cls.query_user_channel(email_lower)
        
        if user_channel == None:
            user_channel = cls()
            user_channel.email_lower = email_lower
        
        user_channel.expired = datetime.datetime.now() + datetime.timedelta(hours=24)
        user_channel.token = channel.create_channel(email_lower,
                                                  duration_minutes=24*60)
        user_channel.put()
        return user_channel
    
    def update_user_channel(self):
        self.expired = datetime.datetime.now() + datetime.timedelta(hours=24)
        self.token = channel.create_channel(self.email_lower,
                                            duration_minutes=24*60)
        self.put()
    
    '''
        To get the token of the channel for user.
        The token is a short lived one (24 hrs) 
        If the token still available, return the existing one.
        Else create a new token for the user
    '''
    @classmethod
    def get_user_channel(cls, email_lower):
        user_channel = cls.query_user_channel(email_lower)
        
        if user_channel != None:
            if user_channel.expired <= datetime.datetime.now():
                user_channel.update_user_channel()
        else:
            user_channel = cls.create_user_channel(email_lower)
        return user_channel
    
    @classmethod
    def get_valid_channels(cls):
        query_result = cls.query(cls.expired > datetime.datetime.now())
        return query_result.fetch()
    
         
'''
class for User, which extends the default webapp2 User model
https://webapp-improved.appspot.com/api/webapp2_extras/appengine/auth/models.html
It has the below params:
    - created
    - updated
    - auth_ids
    - password
Its parent is BusinessGroup
login id is email
'''
class User(BaseModel, webapp2_extras.appengine.auth.models.User):
    email = ndb.StringProperty(required=True)
    email_lower = ndb.ComputedProperty(lambda self: self.email.lower())
    user_role = ndb.KeyProperty(kind=UserRole, required=True, verbose_name='role_name')
    access_level = ndb.ComputedProperty(lambda self: self.user_role.get().access_level)
    business_group = ndb.KeyProperty(required=True, kind=BusinessGroup, verbose_name='business_name')
    #price_plan = ndb.KeyProperty(kind=PricePlan, verbose_name='plan_name')
    business_team = ndb.KeyProperty(kind=BusinessTeam, verbose_name='team_name')
    user_name = ndb.StringProperty(required=True)
    status = ndb.StringProperty(required=True, 
                                default=config.PENDING_STATUS, 
                                choices=config.ACCOUNT_STATUS, 
                                verbose_name=','.join(config.ACCOUNT_STATUS))
    last_login_time = ndb.DateTimeProperty(indexed=False)
    last_logout_time = ndb.DateTimeProperty(indexed=False)
    last_failed_login = ndb.DateTimeProperty(indexed=False)
    failed_login_count = ndb.IntegerProperty(indexed=False, default=0)
    last_host_address = ndb.StringProperty(indexed=False)
    
    unique_or_props = ['email_lower']   
    model_display_name = 'user'
    
    '''
    @property
    def access_level(self):
        user_role = self.user_role.get()
        return user_role.access_level
    '''    
    '''@classmethod
    def query_all(cls):
        return cls.query().order(cls.business_group, cls.user_role, cls.email_lower)
    '''
    @property
    def group_data(self):
        business_group = self.business_group.get().to_dict(cur_user=self)
        return business_group
    
    @property
    def plan_data(self):
        business_group = self.business_group.get()
        price_plan = business_group.price_plan.get().to_dict(cur_user=self)
        return price_plan
    
    @property
    def role_data(self):
        user_role = self.user_role.get().to_dict(cur_user=self)
        return user_role
    
    @property
    def team_data(self):
        if self.business_team != None:
            business_team = self.business_team.get().to_dict(cur_user=self)
        else:
            business_team = None
        return business_team
    
    @property
    def group_status(self):
        business_group = self.business_group.get()
        return business_group.status 
    
    @property
    def team_status(self):
        if self.business_team != None:
            business_team = self.business_team.get()
            return business_team.status
        else:
            return None   
    
    @property
    def group_name(self):
        business_group = self.business_group.get()
        return business_group.business_name
    
    @property
    def team_name(self):
        business_team = self.business_team
        if business_team != None:
            business_team = business_team.get()
            return business_team.team_name
        else:
            return None
    
    @property
    def role_name(self):
        user_role = self.user_role.get()
        return user_role.role_name
    
    @property
    def teams_in_group(self):
        if self.access_level == config.GROUP_ADMIN.access_level:
            teams_in_group = BusinessTeam.get_prop_id_list('team_name', 
                                                       cur_user=self)
        else:
            teams_in_group = None
        return teams_in_group  
    
    @property
    def user_timezone(self):
        #if user team/group is not available, assume the default timezone (+8)
        user_business_team = self.business_team
        user_business_group = self.business_group
        if user_business_team != None:
            tz_offset = int(user_business_team.get().timezone)
        elif user_business_group == None:
            #Default set to Singapore timezone
            tz_offset = 8
        else:
            #Get the group timezone for display
            tz_offset = int(user_business_group.get().timezone)
        user_tz = UserTimeZone(offset=tz_offset)
        return user_tz        
    
    @classmethod
    def prepare_query_order(cls, order_list):
        if order_list == None:
            order_list = [cls.access_level, cls.business_group, cls.email_lower]
        return order_list
    
    def set_password(self, raw_password):
        '''Sets the password for the current user
        :param raw_password:
        The raw password which will be hashed and stored
        '''
        self.password = security.generate_password_hash(raw_password, length=12)
        
    @classmethod
    def get_by_auth_token(cls, user_id, token, subject='auth'):
        """Returns a user object based on a user ID and token.
        :param user_id:
        The user_id of the requesting user.
        :param token:
        The token string to be verified.
        :returns:
        A tuple ``(User, timestamp)``, with a user object and
        the token timestamp, or ``(None, None)`` if both were not found.
        """
        token_key = cls.token_model.get_key(user_id, subject, token)
        user_key = ndb.Key(cls, user_id)
        # Use get_multi() to save a RPC call.
        valid_token, user = ndb.get_multi([token_key, user_key])
        if valid_token and user:
            timestamp = int(time.mktime(valid_token.created.timetuple()))
            return user, timestamp
        
        return None, None
    
    @staticmethod
    def check_user_data(data):
        #print "User data is %s" %model_rec

        response = {}
        if 'user_role' not in data:
            response['message'] = "Please choose a user role."
            response['status'] = False
            return response
        else:
            role_id = int(data['user_role'])
            user_role = UserRole.get_by_id(role_id)
            if user_role.access_level > data['user_access_level']:
                response['message'] = "You are not allowed to use this user role."
                response['status'] = False
                return response
            else:
                del data['user_access_level']
                
        response['status'] = True
        response['message'] = ""
        return response 
    
    @classmethod
    @ExpHandleAll() 
    def create_model_entity(cls, model_rec):
        '''
        Create a new user from the request data
        :param model_rec
            A request object or dictionary
        '''
        email_lower = model_rec.get('email').lower()
        model_entity = cls(id=email_lower)
        
        #Default user role
        '''
        if 'user_role' not in model_rec:
            model_rec['user_role'] = UserRole.query(UserRole.role_name=="Group Admin").get().key.id()
        
            
        if 'user_status' not in model_rec:
            model_rec['status'] = "Pending"
        
        if 'price_plan' not in model_rec:
            model_rec['price_plan'] = PricePlan.query(PricePlan.plan_name=='Personal Free Plan').get().key.id()
        '''

        response = cls.check_user_data(model_rec)
        if response['status'] != True:
            return response
        
        response = model_entity.get_data_from_rec(model_rec=model_rec)
        if response['status'] != True:
            return response
        else:
            data = response['data']
        
        if 'password' in data:
            data['password_raw'] = data['password']
            del data['password']
        else:
            data['password_raw'] = ""
        
        data['verified'] = False

        if DEBUG:
            logging.info("The user data is")
            logging.info(data)

        user_data = cls.create_user(email_lower, None, **data)
        if not user_data[0]: 
            response['message'] = 'Unable to create user because email already exists.'
            response['status'] = False
            return response
        else:
            response['status'] = True
            response['user_data'] = user_data
            return response
        

    @classmethod
    @ExpHandleAll() 
    def delete_model_entity(cls, model_rec):
        #print ("model_rec: %s" %model_rec)
        result = cls.get_id_from_rec(model_rec)
        
        if result['status'] != True:
            return result
        else:
            unique_id = result['id']
            
        tmp_entity = cls.get_by_id(unique_id)
        
        if not tmp_entity:
            result['status'] = False
            result['message'] = "No such user account!" 
            return result
        else:
            tmp_entity.status = config.TERMINATED_STATUS
            tmp_entity.put()
            result['status'] = True
            result['message'] = "The user account has been terminated!"             
            result['entity'] = tmp_entity
            return result 

'''
    Base model for model that handle at the group level.
    All search must limited by the group ID
'''
       
class GroupModel(BaseModel):
    business_group = ndb.KeyProperty(required=True,kind=BusinessGroup, verbose_name='business_name')
    user_created = ndb.KeyProperty(required=True, kind=User, verbose_name='user_name')
    business_team = ndb.KeyProperty(kind=BusinessTeam, verbose_name='team_name')    
    is_group_search = True
    unique_level = config.GROUP_UNIQUE.unique_level
    
class TeamModel(GroupModel):
    business_team = ndb.KeyProperty(required=True,kind=BusinessTeam, verbose_name='team_name')
    is_team_search = True
    unique_level = config.TEAM_UNIQUE.unique_level
'''
    Base model for template class
'''
class TemplateModel(TeamModel):
    template_name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()

class AuditLog(GroupModel):
    email_created = ndb.StringProperty()
    location_created = ndb.StringProperty()
    event_desc = ndb.StringProperty()
    model_display_name = 'audit log'
    
    #Group and team level search
    is_team_search = True

    @classmethod
    def prepare_query_order(cls, order_list):
        if order_list == None:
            order_list = [-cls.tm_created]
        return order_list