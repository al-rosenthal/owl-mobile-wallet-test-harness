from agent_factory.traction.traction_agent_interface import TractionAgentInterface
from agent_factory.issuer_agent_interface import IssuerAgentInterface
from agent_factory.aath.aath_agent_interface import AATHAgentInterface
from agent_test_utils import get_qr_code_from_invitation
from typing import Optional
import requests
import json


class TractionIssuerAgentInterface(IssuerAgentInterface, AATHAgentInterface):

    _schema: dict
    _credential_definition: dict
    _credential_json_dict: dict

    # credentials need to be setup in the traction instance that is running
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.token = self._fetch_token()
        self._schema = {}
        self._credential_definition = {}
        self._credential_json_dict = {}
        self._load_schemas()
        super().__init__(endpoint)

    def _fetch_token(self) -> str:
        print("fetch token")
        # reach out to API with tenant id and api key
        tenant_id = "ac071379-7b24-4275-83d4-c6cc3b62701f"
        api_key = "60b75d3e9cf34fb3a46ae9d8b6cdf169"
        token_endpoint = f"{self.endpoint}/multitenancy/tenant/{tenant_id}/token"
        token_response = requests.post(token_endpoint, json={"api_key": api_key})
        return token_response.json()["token"]

    def _load_schemas(self):
        print("Load schemas")
        photo_schema = json.load(open("features/data/schema_photo_id.json"))
        drivers_license_1 = json.load(
            open("features/data/schema_drivers_license_😀.json")
        )
        drivers_license_2 = json.load(open("features/data/schema_drivers_license.json"))
        photo_revokable = json.load(
            open("features/data/schema_photo_id_revokable.json")
        )

        self._schema_setup(photo_schema)
        self._schema_setup(drivers_license_1)
        self._schema_setup(drivers_license_2)
        self._schema_setup(photo_revokable)

    def _schema_setup(self, schema):
        schema_id = self._get_schema_id_for_name(schema["schema_name"])
        cred_def_id = self._get_cred_def_id_for_name(schema["schema_name"])

        if schema_id == None:
            new_schema = self._register_schema(schema)
            schema_id = new_schema["sent"]["schema"]["id"]

        if cred_def_id == None:
            cred_def_id = self._regsiter_cred_def(schema_id)
        # self._schema = self._get_schema_for_id(schema_id)["schema"]
        # self._credential_definition = self._get_cred_def_for_id(cred_def_id)["credential_definition"]

    def _get_schema_for_id(self, id) -> dict:
        schema_endpoint = f"{self.endpoint}/schemas/{id}"
        return requests.get(schema_endpoint, headers=self._build_headers()).json()

    def _get_cred_def_for_id(self, id) -> dict:
        cred_def_endpoint = f"{self.endpoint}/credential-definitions/{id}"
        return requests.get(cred_def_endpoint, headers=self._build_headers()).json()

    def _get_schema_id_for_name(self, name) -> Optional[str]:
        schema_endpoint = f"{self.endpoint}/schemas/created?schema_name={name}"
        schema_ids = requests.get(schema_endpoint, headers=self._build_headers()).json()
        return (
            schema_ids["schema_ids"][0] if len(schema_ids["schema_ids"]) > 0 else None
        )

    def _get_cred_def_id_for_name(self, name) -> Optional[str]:
        cred_def_endpoint = (
            f"{self.endpoint}/credential-definitions/created?schema_name={name}"
        )
        cred_def_ids = requests.get(
            cred_def_endpoint, headers=self._build_headers()
        ).json()
        return (
            cred_def_ids["credential_definition_ids"][0]
            if len(cred_def_ids["credential_definition_ids"]) > 0
            else None
        )

    def _build_headers(self) -> dict[str, any]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-type": "application/json",
        }

    def _register_schema(self, schema) -> dict:
        print("Register Schema")
        register_endpoint = f"{self.endpoint}/schemas"
        return requests.post(
            register_endpoint, headers=self._build_headers(), json=schema
        ).json()

    def _regsiter_cred_def(self, schema_id, tag="default"):
        print("Register Cred Def")
        register_endpoint = f"{self.endpoint}/credential-definitions"
        return requests.post(
            register_endpoint,
            headers=self._build_headers(),
            json={
                "revocation_registry_size": 1000,
                "schema_id": schema_id,
                "support_revocation": True,
                "tag": tag,
            },
        ).json()

    def get_issuer_type(self) -> str:
        """return the type of issuer as a string TractionIssuer"""
        return "TractionIssuer"

    def create_invitation(
        self, oob=False, print_qrcode=False, save_qrcode=False, qr_code_border=40
    ):
        print("Create OOB invitation")
        # url configured with default values
        oob_invite_url = f"{self.endpoint}/out-of-band/create-invitation?auto_accept=true&create_unique_did=false&multi_use=false"
        payload = {
            "accept": ["didcomm/aip1", "didcomm/aip2;env=rfc19"],
            "alias": "Sauce Labs Device",
            "goal": "",
            "goal_code": "",
            "handshake_protocols": [
                "https://didcomm.org/didexchange/1.0",
                "https://didcomm.org/connections/1.0",
            ],
            "my_label": "",
            "protocol_version": "1.1",
            "use_public_did": False,
        }
        invitation_response = requests.post(
            oob_invite_url, json=payload, headers=self._build_headers()
        ).json()
        qr_code = get_qr_code_from_invitation(
            invitation_response,
            print_qr_code=print_qrcode,
            save_qr_code=save_qrcode,
            qr_code_border=qr_code_border,
        )
        self.invitation_json = invitation_response
        self._oob = True
        return qr_code

    def connected(self):
        print("Check connection status")
        connection_id = ""
        if self._oob == True:
            print("OOB CONNECTION")
            # fetch connection ID from connections
            invite_id = self.invitation_json["invi_msg_id"]
            connection_fetch_rule = f"{self.endpoint}/connections?invitation_msg_id={invite_id}&limit=100&offset=0"
            connection_response = requests.get(
                connection_fetch_rule, headers=self._build_headers()
            )
            results = connection_response.json()
            if results["results"]:
                connection_id = results["results"][0]["connection_id"]
            else:
                raise Exception("OOB Connection record is not found")

        else:
            connection_id = self.invitation_json["connection_id"]
        self._connection_id = connection_id
        connection_ping_url = f"{self.endpoint}/connections/{connection_id}/send-ping"
        ping_response = requests.post(
            connection_ping_url, json={}, headers=self._build_headers()
        )
        return ping_response.status_code == 200

    def revoke_credential(self):
        pass

    def send_credential(
        self, version=2, schema=None, credential_offer=None, revokable=False
    ):
        print("Traction: send credential")
        issue_credential_url = f"{self.endpoint}/issue-credential-2.0/send"

        if credential_offer:
            cred_data = credential_offer["attributes"]
        else:
            cred_data = [
                {"name": "first_name", "value": "Sauce"},
                {"name": "last_name", "value": "Test"},
            ]
        payload = {
            "auto_remove": True,
            "comment": "string",
            "connection_id": self._connection_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": cred_data,
            },
            "filter": {"indy": {"cred_def_id": self._credential_definition["id"]}},
            "trace": True,
            "verification_method": "string",
        }

        self._credential_definition = {
            "schema_id": self._schema["id"],
            "tag": self._schema["name"],
        }

        response = requests.post(
            issue_credential_url, json=payload, headers=self._build_headers()
        )
        json_response = response.json()
        if response.status_code == 200:
            self.credential_json = json_response
            self._credential_json_dict[self._credential_definition["tag"]] = (
                json_response
            )
        else:
            raise Exception(
                f"There was an error sending credential to: {self._connection_id}"
            )

    def _get_public_did(self):
        did_endpoint = f"{self.endpoint}/wallet/did?method=sov&posture=public"
        wallet_dids = requests.get(did_endpoint).json()
        if len(wallet_dids["results"]) <= 0:
            raise Exception(
                "Public DID not available, traction tenant needs to be an issuer"
            )

        self._my_public_did = wallet_dids["results"][0]["did"]
        return self._my_public_did
