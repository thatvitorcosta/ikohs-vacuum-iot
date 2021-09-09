import boto3, json, configparser
from pycognito.aws_srp import AWSSRP

class Ikohs:

    AWS = {
        "CredentialsProvider": {
            "CognitoIdentity": {
            "Default": {
                "PoolId": "eu-central-1:d297d27e-a693-4f36-9de6-d74244e812ee",
                "Region": "eu-central-1"
            }
            }
        },
        "CognitoUserPool": {
            "Default": {
            "PoolId": "eu-central-1_kZO9vyiK7",
            "AppClientId": "1temi4s8l4dh32u28bdf67hpg7",
            "AppClientSecret": "11glcfuvp01r191pc6f2mghtj5ld2boc158ipb66iofav0e1nd6f",
            "Region": "eu-central-1"
            }
        }
    }
    UserAuth = {}
    currentConfig = {
        'AccessToken': '',
        'RefreshToken': '',
        'IdToken': '',
        'IdentityId': '',
        'AccessKeyId': '',
        'SecretKey': '',
        'SessionToken': ''
    }

    def __init__(self, auth):
        self.UserAuth = auth
        self.config = configparser.ConfigParser()
        self.config.read('ikhos.ini')
        if not self.config.has_section(self.UserAuth['username']):
            self.authenticateAWS();
        else:
            self.currentConfig = self.config[self.UserAuth['username']]    
    
    def authenticateAWS(self):
        client = boto3.client('cognito-idp', region_name=self.AWS["CognitoUserPool"]["Default"]["Region"])
        aws = AWSSRP(username=self.UserAuth["username"], password=self.UserAuth["password"], pool_id=self.AWS["CognitoUserPool"]["Default"]["PoolId"],
                    client_id=self.AWS["CognitoUserPool"]["Default"]["AppClientId"], client_secret=self.AWS["CognitoUserPool"]["Default"]["AppClientSecret"], client=client)
        tokens = aws.authenticate_user()
        self.currentConfig['AccessToken'] = tokens['AuthenticationResult']['AccessToken']
        self.currentConfig['RefreshToken'] = tokens['AuthenticationResult']['RefreshToken']
        self.currentConfig['IdToken'] = tokens['AuthenticationResult']['IdToken']

        client = boto3.client('cognito-identity', region_name=self.AWS["CredentialsProvider"]["CognitoIdentity"]["Default"]["Region"])
        response = client.get_id(
            IdentityPoolId=self.AWS["CredentialsProvider"]["CognitoIdentity"]["Default"]["PoolId"],
            Logins={
                'cognito-idp.'+self.AWS["CognitoUserPool"]["Default"]["Region"]+'.amazonaws.com/'+self.AWS["CognitoUserPool"]["Default"]["PoolId"]: self.currentConfig['IdToken']
            }
        )
        self.currentConfig['IdentityId'] = response['IdentityId']

        response = client.get_credentials_for_identity(
            IdentityId=self.currentConfig['IdentityId'],
            Logins={
                'cognito-idp.'+self.AWS["CognitoUserPool"]["Default"]["Region"]+'.amazonaws.com/'+self.AWS["CognitoUserPool"]["Default"]["PoolId"]: self.currentConfig['IdToken']
            }
        )
        self.currentConfig['AccessKeyId'] = response['Credentials']['AccessKeyId']
        self.currentConfig['SecretKey'] = response['Credentials']['SecretKey']
        self.currentConfig['SessionToken'] = response['Credentials']['SessionToken']

        self.config[self.UserAuth['username']] = self.currentConfig
        with open('ikhos.ini', 'w') as configfile:
            self.config.write(configfile)
    
    def getVacuum(self):
        client = boto3.client('lambda',
        region_name=self.AWS["CognitoUserPool"]["Default"]["Region"],
        aws_access_key_id=self.currentConfig['AccessKeyId'],
        aws_secret_access_key=self.currentConfig['SecretKey'],
        aws_session_token=self.currentConfig['SessionToken'])
        
        payload = {"Identity_Id":self.currentConfig['IdentityId']};
        response = client.invoke(
            FunctionName='Ikohs_User_Query_All_Thing',
            Payload=json.dumps(payload, indent=2).encode('utf-8')
        )

        payload = json.loads(response['Payload'].read().decode('utf-8'))
        self.thingId = payload['Room'][0]['Thing'][0]['Thing_Name']
        return self.getState(self.thingId)
    
    def getState(self, thingId):
        client = boto3.client('iot-data',
        verify=False,
        region_name=self.AWS["CognitoUserPool"]["Default"]["Region"],
        aws_access_key_id=self.currentConfig['AccessKeyId'],
        aws_secret_access_key=self.currentConfig['SecretKey'],
        aws_session_token=self.currentConfig['SessionToken'])

        response = client.get_thing_shadow(
            thingName=thingId
        )
        payload = json.loads(response['payload'].read().decode('utf-8'))
        payload['state']['reported']['thingId']=self.thingId;
        return payload['state']['reported']
    
    def doAction(self, thingId:str, action: str):
        actions = {
            "start": {"state":{"desired":{"offset_minutes":0,"working_status":"AutoClean","offset_hours":0}}},
            "stop": {"state":{"desired":{"offset_minutes":0,"working_status":"Standby","offset_hours":0}}},
            "fanQuiet": {"state":{"desired":{"offset_minutes":0,"offset_hours":0,"fan_status":"Normal"}}},
            "fanStrong": {"state":{"desired":{"offset_minutes":0,"offset_hours":0,"fan_status":"Strong"}}},
            "mopFast": {"state":{"desired":{"offset_minutes":0,"offset_hours":0,"water_level":"High"}}},
            "mop": {"state":{"desired":{"offset_minutes":0,"offset_hours":0,"water_level":"Default"}}},
            "mopSlow": {"state":{"desired":{"offset_minutes":0,"offset_hours":0,"water_level":"Low"}}},
            "returnHome": {"state":{"desired":{"offset_minutes":0,"working_status":"BackCharging","offset_hours":0}}},
            "spotClean": {"state":{"desired":{"offset_minutes":0,"working_status":"SpotClean","offset_hours":0}}},
            "edgeClean": {"state":{"desired":{"offset_minutes":0,"working_status":"EdgeClean","offset_hours":0}}},
            "goFoward": {"state":{"desired":{"offset_minutes":0,"working_status":"MoveFront","offset_hours":0}}},
            "goBackward": {"state":{"desired":{"offset_minutes":0,"working_status":"MoveBack","offset_hours":0}}},
            "goLeft": {"state":{"desired":{"offset_minutes":0,"working_status":"MoveLeft","offset_hours":0}}},
            "goRight": {"state":{"desired":{"offset_minutes":0,"working_status":"MoveRight","offset_hours":0}}},
            "stopMove": {"state":{"desired":{"offset_minutes":0,"working_status":"MoveStop","offset_hours":0}}},
        }
        client = boto3.client('iot-data',
        verify=False,
        region_name=self.AWS["CognitoUserPool"]["Default"]["Region"],
        aws_access_key_id=self.currentConfig['AccessKeyId'],
        aws_secret_access_key=self.currentConfig['SecretKey'],
        aws_session_token=self.currentConfig['SessionToken'])
        
        response = client.update_thing_shadow(
            thingName=thingId,
            payload=json.dumps(actions[action], indent=2).encode('utf-8')
        )
        return json.loads(response['payload'].read().decode('utf-8'))
