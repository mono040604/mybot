from pathlib import Path
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

class ProviderConfig(BaseSettings):
    api_key: str = ""  # FIX: 缺类型注解
    api_base: str = ""  # FIX: 缺类型注解
    model: str = ""
    model_config = ConfigDict(extra="allow")

class AgentDefaults(BaseSettings):
    model: str = "gpt-4o-mini"
    provider: str = "openai"
    max_tool_iterations: int = Field(default=15, ge=1, le=100)
    max_result_chars: int = Field(default=80_000, ge=1_000)
    context_window_tokens: int = Field(default=128_000, ge=1_000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    model_config = ConfigDict(extra="allow")

class ToolsConfig(BaseSettings):
    restrict_to_workspace: bool = True

    class FileTools(BaseSettings):
        enabled: bool = True
        model_config = ConfigDict(extra="allow")
    
    class ExecTools(BaseSettings):
        enabled: bool = True
        model_config = ConfigDict(extra="allow")
    
    class WebTools(BaseSettings):
        enabled: bool = True  # FIX: enable→enabled
        model_config = ConfigDict(extra="allow")
    
    files: FileTools = Field(default_factory=FileTools)
    exec: ExecTools = Field(default_factory=ExecTools)
    web: WebTools = Field(default_factory=WebTools)

    model_config = ConfigDict(extra="allow")

class GatewayConfig(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    model_config = ConfigDict(extra="allow")

class Config(BaseSettings):
    agents: AgentDefaults = Field(default_factory=AgentDefaults)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)

    @property
    def workspace_path(self) -> Path:
        return Path.cwd()
    def get_provider(self, model: str) -> ProviderConfig:
        for name, cfg in self.providers.items():
            if cfg.model == model:
                return cfg
        return self.providers.get(self.agents.provider, ProviderConfig())
   
    model_config = ConfigDict(extra="allow")