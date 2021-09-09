"""Support for Ikohs S15 vacuums."""
import logging
import voluptuous as vol

import boto3, json, configparser
from pycognito.aws_srp import AWSSRP

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STOP,
    StateVacuumEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = "vacuums"
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"

ENTITY_ID_FORMAT = VACUUM_DOMAIN + ".{}"
_VALID_STATES = [
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_PAUSED,
    STATE_IDLE,
    STATE_RETURNING,
    STATE_ERROR,
]

VACUUM_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {   
            vol.Required("username"): cv.string,
            vol.Required("password"): cv.string,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_VACUUMS): vol.Schema({cv.slug: VACUUM_SCHEMA})}
)


async def _async_create_entities(hass, config):
    """Create the Ikohs Vacuums."""



    vacuums = []
    for device, device_config in config[CONF_VACUUMS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        username = device_config.get("username")
        password = device_config.get("password")

        ikhos = Ikohs({'username': username, 'password': password})
        vacuum = ikhos.getVacuum()

        vacuums.append(
            IkohsVacuum(
                hass,
                device,
                friendly_name,
                vacuum['working_status'],
                vacuum['battery_level'],
                vacuum['fan_status'],
                vacuum['connected'],
                vacuum['thingId'],
            )
        )

    return vacuums


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template vacuums."""
    async_add_entities(await _async_create_entities(hass, config))


class IkohsVacuum(StateVacuumEntity):
    """A template vacuum component."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        battery_level_template,
        fan_speed_template,
        availability_template,
        unique_id,
    ):
        """Initialize the vacuum."""
        super().__init__(
            attribute_templates=attribute_templates,
            availability_template=availability_template,
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name

        self._template = state_template
        self._battery_level_template = battery_level_template
        self._fan_speed_template = fan_speed_template
        self._supported_features = SUPPORT_START

        domain = __name__.split(".")[-2]

        self._start_script = Script(hass, start_action, friendly_name, domain)

        self._pause_script = None
        if pause_action:
            self._pause_script = Script(hass, pause_action, friendly_name, domain)
            self._supported_features |= SUPPORT_PAUSE

        self._stop_script = None
        if stop_action:
            self._stop_script = Script(hass, stop_action, friendly_name, domain)
            self._supported_features |= SUPPORT_STOP

        self._return_to_base_script = None
        if return_to_base_action:
            self._return_to_base_script = Script(
                hass, return_to_base_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_RETURN_HOME

        self._clean_spot_script = None
        if clean_spot_action:
            self._clean_spot_script = Script(
                hass, clean_spot_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_CLEAN_SPOT

        self._locate_script = None
        if locate_action:
            self._locate_script = Script(hass, locate_action, friendly_name, domain)
            self._supported_features |= SUPPORT_LOCATE

        self._set_fan_speed_script = None
        if set_fan_speed_action:
            self._set_fan_speed_script = Script(
                hass, set_fan_speed_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_FAN_SPEED

        self._state = None
        self._battery_level = None
        self._fan_speed = None

        if self._template:
            self._supported_features |= SUPPORT_STATE
        if self._battery_level_template:
            self._supported_features |= SUPPORT_BATTERY

        self._unique_id = unique_id

        # List of valid fan speeds
        self._fan_speed_list = ["Normal", "Strong"]

    @property
    def name(self):
        """Return the display name of this vacuum."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this vacuum."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._state

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list:
        """Get the list of available fan speeds."""
        return self._fan_speed_list

    async def async_start(self):
        """Start or resume the cleaning task."""
        await self._start_script.async_run(context=self._context)

    async def async_pause(self):
        """Pause the cleaning task."""
        if self._pause_script is None:
            return

        await self._pause_script.async_run(context=self._context)

    async def async_stop(self, **kwargs):
        """Stop the cleaning task."""
        if self._stop_script is None:
            return

        await self._stop_script.async_run(context=self._context)

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self._return_to_base_script is None:
            return

        await self._return_to_base_script.async_run(context=self._context)

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self._clean_spot_script is None:
            return

        await self._clean_spot_script.async_run(context=self._context)

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        if self._locate_script is None:
            return

        await self._locate_script.async_run(context=self._context)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self._set_fan_speed_script is None:
            return

        if fan_speed in self._fan_speed_list:
            self._fan_speed = fan_speed
            await self._set_fan_speed_script.async_run(
                {ATTR_FAN_SPEED: fan_speed}, context=self._context
            )
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s. Expected: %s",
                fan_speed,
                self._fan_speed_list,
            )

    async def async_added_to_hass(self):
        """Register callbacks."""
        if self._template is not None:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        if self._fan_speed_template is not None:
            self.add_template_attribute(
                "_fan_speed",
                self._fan_speed_template,
                None,
                self._update_fan_speed,
            )
        if self._battery_level_template is not None:
            self.add_template_attribute(
                "_battery_level",
                self._battery_level_template,
                None,
                self._update_battery_level,
                none_on_template_error=True,
            )
        await super().async_added_to_hass()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            # This is legacy behavior
            self._state = STATE_UNKNOWN
            if not self._availability_template:
                self._attr_available = True
            return

        # Validate state
        if result in _VALID_STATES:
            self._state = result
        elif result == STATE_UNKNOWN:
            self._state = None
        else:
            _LOGGER.error(
                "Received invalid vacuum state: %s. Expected: %s",
                result,
                ", ".join(_VALID_STATES),
            )
            self._state = None

    @callback
    def _update_battery_level(self, battery_level):
        try:
            battery_level_int = int(battery_level)
            if not 0 <= battery_level_int <= 100:
                raise ValueError
        except ValueError:
            _LOGGER.error(
                "Received invalid battery level: %s. Expected: 0-100", battery_level
            )
            self._battery_level = None
            return

        self._battery_level = battery_level_int

    @callback
    def _update_fan_speed(self, fan_speed):
        if isinstance(fan_speed, TemplateError):
            # This is legacy behavior
            self._fan_speed = None
            self._state = None
            return

        if fan_speed in self._fan_speed_list:
            self._fan_speed = fan_speed
        elif fan_speed == STATE_UNKNOWN:
            self._fan_speed = None
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s. Expected: %s",
                fan_speed,
                self._fan_speed_list,
            )
            self._fan_speed = None
            
class Ikohs:

    AWS = {}
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
        with open('awsconfiguration.json') as f:
            self.AWS = json.load(f)
        self.config = configparser.ConfigParser()
        self.config.read('ikhos.ini')
        if not self.config.has_section(self.UserAuth['username']):
            self.authenticate();
        else:
            self.currentConfig = self.config[self.UserAuth['username']]    
    
    def authenticate(self):
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
