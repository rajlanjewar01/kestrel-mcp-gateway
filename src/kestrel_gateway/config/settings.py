from pydantic_settings import BaseSettings
from pydantic import Field


class GatewaySettings(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    # SYS-1 WMS
    wms_base_url: str = "http://localhost:8081"
    wms_api_key: str = Field(..., alias="WMS_API_KEY")

    # SYS-2 TMS
    tms_base_url: str = "http://localhost:8082"
    tms_client_id: str = Field(..., alias="TMS_CLIENT_ID")
    tms_client_secret: str = Field(..., alias="TMS_CLIENT_SECRET")

    # SYS-3 Ticketing
    ticketing_base_url: str = "http://localhost:8083"
    ticketing_bearer_token: str = Field(..., alias="TICKETING_BEARER_TOKEN")

    # SYS-4 Contracts
    contracts_base_url: str = "http://localhost:8084"
    contracts_cert_path: str = ""
    contracts_key_path: str = ""

    # Gateway
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8080
    kill_switch_path: str = "kill_switch.json"
    audit_log_path: str = "audit_logs"


def load_settings(**overrides) -> GatewaySettings:
    return GatewaySettings(**overrides)
