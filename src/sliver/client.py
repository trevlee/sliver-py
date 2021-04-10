"""
Sliver Implant Framework
Copyright (C) 2021  Bishop Fox
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


import grpc
from .pb.commonpb import common_pb2
from .pb.clientpb import client_pb2
from .pb.sliverpb import sliver_pb2
from .pb.rpcpb.services_pb2_grpc import SliverRPCStub
from .config import SliverClientConfig
from typing import Union


KB = 1024
MB = 1024 * KB
GB = 1024 * MB
TIMEOUT = 60


class BaseClient(object):

    # 2GB triggers an overflow error in the gRPC library so we do 2GB-1
    MAX_MESSAGE_LENGTH = (2 * GB) - 1

    KEEP_ALIVE_TIMEOUT = 10000
    CERT_COMMON_NAME = 'multiplayer'

    def __init__(self, config: SliverClientConfig):
        self.config = config
        self._channel: grpc.Channel = None
        self._stub: SliverRPCStub = None

    @property
    def target(self) -> str:
        return "%s:%d" % (self.config.lhost, self.config.lport,)

    @property
    def credentials(self) -> grpc.ChannelCredentials:
        return grpc.ssl_channel_credentials(
            root_certificates=self.config.ca_certificate.encode(),
            private_key=self.config.private_key.encode(),
            certificate_chain=self.config.certificate.encode(),
        )
    
    @property
    def options(self):
        return [
            ('grpc.keepalive_timeout_ms', self.KEEP_ALIVE_TIMEOUT),
            ('grpc.ssl_target_name_override', self.CERT_COMMON_NAME),
            ('grpc.max_send_message_length', self.MAX_MESSAGE_LENGTH),
            ('grpc.max_receive_message_length', self.MAX_MESSAGE_LENGTH),
        ]

    def is_connected(self) -> bool:
        return self._channel is not None


class BaseSession(object):

    def __init__(self, session: client_pb2.Session, channel: grpc.Channel, timeout=TIMEOUT):
        self._channel = channel
        self._session = session
        self._stub = SliverRPCStub(channel)
        self.timeout = timeout

    def request(self, pb):
        '''
        Set request attributes based on current session, I'd prefer to return a generic Request
        object, but protobuf for whatever reason doesn't let you assign this type of field directly.

        `pb` in this case is any protobuf message with a .Request field.
        '''
        pb.Request.SessionID = self._session.ID
        pb.Request.Timeout = self.timeout-1
        return pb

    @property
    def session_id(self) -> int:
        return self._session.ID
    
    @property
    def name(self) -> str:
        return self._session.Name
    
    @property
    def hostname(self) -> int:
        return self._session.Hostname
    
    @property
    def uuid(self) -> str:
        return self._session.UUID
    
    @property
    def username(self) -> str:
        return self._session.Username
    
    @property
    def uid(self) -> str:
        return self._session.UID

    @property
    def gid(self) -> str:
        return self._session.GID

    @property
    def os(self) -> str:
        return self._session.OS

    @property
    def arch(self) -> str:
        return self._session.Arch

    @property
    def transport(self) -> str:
        return self._session.Transport

    @property
    def remote_address(self) -> str:
        return self._session.RemoteAddress

    @property
    def pid(self) -> int:
        return self._session.PID

    @property
    def filename(self) -> str:
        return self._session.Filename

    @property
    def last_checkin(self) -> str:
        return self._session.LastCheckin

    @property
    def active_c2(self) -> str:
        return self._session.ActiveC2

    @property
    def version(self) -> str:
        return self._session.Version

    @property
    def evasion(self) -> bool:
        return self._session.Evasion

    @property
    def is_dead(self) -> bool:
        return self._session.IsDead

    @property
    def reconnect_interval(self) -> int:
        return self._session.ReconnectInterval

    @property
    def proxy_url(self) -> str:
        return self._session.ProxyURL


class AsyncInteractiveSession(BaseSession):

    async def ping(self) -> sliver_pb2.Ping:
        ping = sliver_pb2.Ping()
        ping.Request = self.request()
        return (await self._stub.Ping(ping, timeout=self.timeout))

    async def ps(self) -> sliver_pb2.Ps:
        ps = sliver_pb2.PsReq()
        return (await self._stub.Ps(self.request(ps), timeout=self.timeout))
    
    async def terminate(self, pid: int, force=False) -> sliver_pb2.Terminate:
        terminator = sliver_pb2.TerminateReq()
        terminator.Pid = pid
        terminator.Force = force
        return (await self._stub.Terminate(self.request(terminator), timeout=self.timeout))

    async def ifconfig(self) -> sliver_pb2.Ifconfig:
        return (await self._stub.Ifconfig(self.request(sliver_pb2.IfconfigReq(), timeout=self.timeout)))
    
    async def netstat(self, tcp: bool, udp: bool, ipv4: bool, ipv6: bool, listening=True) -> list[sliver_pb2.SockTabEntry]:
        net = sliver_pb2.NetstatReq()
        net.TCP = tcp
        net.UDP = udp
        net.IP4 = ipv4
        net.IP6 = ipv6
        net.Listening = listening
        stat = await self._stub.Netstat(self.request(net), timeout=self.timeout)
        return list(stat.Entries)
    
    async def ls(self, remote_path: str) -> sliver_pb2.Ls:
        ls = sliver_pb2.LsReq()
        ls.Path = remote_path
        return (await self._stub.Ls(self.request(ls), timeout=self.timeout))

    async def cd(self, remote_path: str) -> sliver_pb2.Pwd:
        cd = sliver_pb2.CdReq()
        cd.Path = remote_path
        return (await self._stub.Cd(self.request(cd), timeout=self.timeout))

    async def pwd(self) -> sliver_pb2.Pwd:
        pwd = sliver_pb2.PwdReq()
        return (await self._stub.Pwd(self.request(pwd), timeout=self.timeout))

    async def rm(self, remote_path: str, recursive=False, force=False) -> sliver_pb2.Rm:
        rm = sliver_pb2.RmReq()
        rm.Path = remote_path
        rm.Recursive = recursive
        rm.Force = force
        return (await self._stub.Rm(self.request(rm), timeout=self.timeout))

    async def mkdir(self, remote_path: str) -> sliver_pb2.Mkdir:
        make = sliver_pb2.MkdirReq()
        make.Path = remote_path
        return (await self._stub.Mkdir(self.request(make), timeout=self.timeout))

    async def download(self, remote_path: str) -> sliver_pb2.Download:
        download = sliver_pb2.DownloadReq()
        download.Path = remote_path
        return (await self._stub.Download(self.request(download), timeout=self.timeout))

    async def upload(self, remote_path: str, data: bytes, encoder='') -> sliver_pb2.Upload:
        upload = sliver_pb2.UploadReq()
        upload.Path = remote_path
        upload.Data = data
        upload.Encoder = encoder
        return (await self._stub.Upload(self.request(upload), timeout=self.timeout))

    async def process_dump(self, pid: int) -> sliver_pb2.ProcessDump:
        procdump = sliver_pb2.ProcessDumpReq()
        procdump.Pid = pid
        return (await self._stub.ProcessDump(self.request(procdump), timeout=self.timeout))

    async def run_as(self, username: str, process_name: str, args: str) -> sliver_pb2.RunAs:
        run_as = sliver_pb2.RunAsReq()
        run_as.Username = username
        run_as.ProcessName = process_name
        run_as.Args = args
        return (await self._stub.RunAs(self.request(run_as), timeout=self.timeout))

    async def impersonate(self, username: str) -> sliver_pb2.Impersonate:
        impersonate = sliver_pb2.ImpersonateReq()
        impersonate.Username = username
        return (await self._stub.Impersonate(self.request(impersonate), timeout=self.timeout))
    
    async def revert_to_self(self) -> sliver_pb2.RevToSelf:
        return (await self._stub.RevToSelf(self.request(sliver_pb2.RevToSelfReq()), timeout=self.timeout))
    
    async def get_system(self, hosting_process: str, config: client_pb2.ImplantConfig) -> sliver_pb2.GetSystem:
        system = client_pb2.GetSystemReq()
        system.HostingProcess = hosting_process
        system.Config = config
        return (await self._stub.GetSystem(self.request(system), timeout=self.timeout))
    
    async def execute_shellcode(self, data: bytes, rwx: bool, pid: int, encoder='') -> sliver_pb2.Task:
        return (await self.task(data, rwx, pid, encoder))

    async def task(self, data: bytes, rwx: bool, pid: int, encoder='') -> sliver_pb2.Task:
        task = sliver_pb2.TaskReq()
        task.Encoder = encoder
        task.RWXPages = rwx
        task.Pid = pid
        task.Data = data
        return (await self._stub.Task(self.request(task), timeout=self.timeout))
    
    async def msf(self, payload: str, lhost: str, lport: int, encoder: str, iterations: int) -> None:
        msf = client_pb2.MSFReq()
        msf.Payload = payload
        msf.LHost = lhost
        msf.LPort = lport
        msf.Encoder = encoder
        msf.Iterations = iterations
        return (await self._stub.Msf(self.request(msf), timeout=self.timeout))

    async def msf_remote(self, payload: str, lhost: str, lport: int, encoder: str, iterations: int, pid: int) -> None:
        msf = client_pb2.MSFRemoteReq()
        msf.Payload = payload
        msf.LHost = lhost
        msf.LPort = lport
        msf.Encoder = encoder
        msf.Iterations = iterations
        msf.PID = pid
        return (await self._stub.Msf(self.request(msf), timeout=self.timeout))
    
    async def execute_assembly(self, assembly: bytes, arguments: str, process: str, is_dll: bool, arch: str, class_name: str, method: str, app_domain: str) -> sliver_pb2.ExecuteAssembly:
        asm = sliver_pb2.ExecuteAssemblyReq()
        asm.Assembly = assembly
        asm.Arguments = arguments
        asm.Process = process
        asm.IsDLL = is_dll
        asm.Arch = arch
        asm.ClassName = class_name
        asm.AppDomain = app_domain
        return (await self._stub.ExecuteAssembly(self.request(asm), timeout=self.timeout))
    
    async def migrate(self, pid: int, config: client_pb2.ImplantConfig) -> sliver_pb2.Migrate:
        migrate = client_pb2.MigrateReq()
        migrate.Pid = pid
        migrate.Config = config
        return (await self._stub.Migrate(self.request(migrate), timeout=self.timeout))

    async def execute(self, exe: str, args: list[str], output: bool) -> sliver_pb2.Execute:
        exec = sliver_pb2.ExecuteReq()
        exec.Path = exe
        exec.Args = args
        exec.Output = output
        return (await self._stub.Execute(self.request(exec), timeout=self.timeout))
    
    async def execute_token(self, exe: str, args: list[str], output: bool) -> sliver_pb2.Execute:
        execToken = sliver_pb2.ExecuteTokenReq()
        execToken.Path = exe
        execToken.Args = args
        execToken.Output = output
        return (await self._stub.ExecuteToken(self.request(execToken), timeout=self.timeout))
    
    async def sideload(self, data: bytes, process_name: str, arguments: str, entry_point: str, kill: bool) -> sliver_pb2.Sideload:
        side = sliver_pb2.SideloadReq()
        side.Data = data
        side.ProcessName = process_name
        side.Args = arguments
        side.EntryPoint = entry_point
        side.Kill = kill
        return (await self._stub.Sideload(self.request(side), timeout=self.timeout))
    
    async def spawn_dll(self, data: bytes, process_name: str, arguments: str, entry_point: str, kill: bool) -> sliver_pb2.SpawnDll:
        spawn = sliver_pb2.InvokeSpawnDllReq()
        spawn.Data = data
        spawn.ProcessName = process_name
        spawn.Args = arguments
        spawn.EntryPoint = entry_point
        spawn.Kill = kill
        return (await self._stub.SpawnDll(self.request(spawn), timeout=self.timeout))
    
    async def screenshot(self) -> sliver_pb2.Screenshot:
        return (await self._stub.Screenshot(self.request(sliver_pb2.ScreenshotReq()), timeout=self.timeout))
    
    async def named_pipes(self, pipe_name: str) -> sliver_pb2.NamedPipes:
        pipe = sliver_pb2.NamedPipesReq()
        pipe.PipeName = pipe_name
        return (await self._stub.NamedPipes(self.request(pipe), timeout=self.timeout))

    async def tcp_pivot_listener(self, address: str) -> sliver_pb2.TCPPivot:
        pivot = sliver_pb2.TCPPivotReq()
        pivot.Address = address
        return (await self._stub.TCPListener(self.request(pivot), timeout=self.timeout))
    
    async def pivots(self) -> list[sliver_pb2.PivotEntry]:
        pivots = await self._stub.ListPivots(self.request(sliver_pb2.PivotListReq()), timeout=self.timeout)
        return list(pivots.Entries)

    async def start_service(self, name: str, description: str, exe: str, hostname: str, arguments: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StartServiceReq()
        svc.ServiceName = name
        svc.ServiceDescription = description
        svc.BinPath = exe
        svc.Hostname = hostname
        svc.Arguments = arguments
        return (await self._stub.StartService(self.request(svc), timeout=self.timeout))
    
    async def stop_service(self, name: str, hostname: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StopServiceReq()
        svc.ServiceInfo.ServiceName = name
        svc.ServiceInfo.Hostname = hostname
        return (await self._stub.StopService(self.request(svc), timeout=self.timeout))

    async def remove_service(self, name: str, hostname: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StopServiceReq()
        svc.ServiceInfo.ServiceName = name
        svc.ServiceInfo.Hostname = hostname
        return (await self._stub.RemoveService(self.request(svc), timeout=self.timeout))

    async def make_token(self, username: str, password: str, domain: str) -> sliver_pb2.MakeToken:
        make = sliver_pb2.MakeTokenReq()
        make.Username = username
        make.Password = password
        make.Domain = domain
        return (await self._stub.MakeToken(self.request(make), timeout=self.timeout))

    async def get_env(self, name: str) -> sliver_pb2.EnvInfo:
        env = sliver_pb2.EnvReq()
        env.Name = name
        return (await self._stub.GetEnv(self.request(env), timeout=self.timeout))
    
    async def set_env(self, name: str, value: str) -> sliver_pb2.SetEnv:
        env = sliver_pb2.SetEnvReq()
        env.EnvVar.Key = name
        env.EnvVar.Value = value
        return (await self._stub.SetEnv(self.request(env), timeout=self.timeout))
    
    async def backdoor(self, remote_path: str, profile_name: str) -> sliver_pb2.Backdoor:
        backdoor = sliver_pb2.BackdoorReq()
        backdoor.FilePath = remote_path
        backdoor.ProfileName = profile_name
        return (await self._stub.Backdoor(self.request(backdoor), timeout=self.timeout))
    
    async def registry_read(self, hive: str, reg_path: str, key: str, hostname: str) -> sliver_pb2.RegistryRead:
        reg = sliver_pb2.RegistryReadReq()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        return (await self._stub.RegistryRead(self.request(reg), timeout=self.timeout))

    async def registry_write(self, hive: str, reg_path: str, key: str, hostname: str, string_value: str, byte_value: bytes, dword_value: int, qword_value: int, reg_type: sliver_pb2.RegistryType) -> sliver_pb2.RegistryWrite:
        reg = sliver_pb2.RegistryWriteReq()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        reg.StringValue = string_value
        reg.ByteValue = byte_value
        reg.DWordValue = dword_value
        reg.QWordValue = qword_value
        reg.Type = reg_type
        return (await self._stub.RegistryWrite(self.request(reg), timeout=self.timeout))
    
    async def registry_create_key(self, hive: str, reg_path: str, key: str, hostname: str) -> sliver_pb2.RegistryCreateKey:
        reg = sliver_pb2.RegistryCreateKey()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        return (await self._stub.RegistryWrite(self.request(reg), timeout=self.timeout))


class SliverAsyncClient(BaseClient):

    ''' Asyncio client implementation '''

    async def connect(self) -> None:
        self._channel = grpc.aio.secure_channel(
            target=self.target,
            credentials=self.credentials,
            options=self.options,
        )
        self._stub = SliverRPCStub(self._channel)

    async def interact(self, session_id: int, timeout=TIMEOUT) -> Union[AsyncInteractiveSession, None]:
        session = await self.session_by_id(session_id, timeout)
        if session is not None:
            return AsyncInteractiveSession(session, self._channel, timeout)

    async def session_by_id(self, session_id: int, timeout=TIMEOUT) -> Union[client_pb2.Session, None]:
        sessions = await self.sessions(timeout)
        for session in sessions:
            if session.ID == session_id:
                return session
        return None

    async def version(self, timeout=TIMEOUT) -> client_pb2.Version:
        return (await self._stub.GetVersion(common_pb2.Empty(), timeout=timeout))

    async def operators(self, timeout=TIMEOUT) -> list[client_pb2.Operator]:
        operators = await self._stub.GetOperators(common_pb2.Empty(), timeout=timeout)
        return list(operators.Operators)

    async def sessions(self, timeout=TIMEOUT) -> list[client_pb2.Session]:
        sessions: client_pb2.Sessions = await self._stub.GetSessions(common_pb2.Empty(), timeout=timeout)
        return list(sessions.Sessions)

    async def kill_session(self, session_id: int, force=False, timeout=TIMEOUT) -> None:
        kill = sliver_pb2.KillSessionReq()
        kill.Request.SessionID = session_id
        kill.Request.Timeout = timeout-1
        kill.Force = force
        await self._stub.KillSession(kill, timeout=timeout)

    async def update_session(self, session_id: int, name: str, timeout=TIMEOUT) -> client_pb2.Session:
        update = client_pb2.UpdateSession()
        update.SessionID = session_id
        update.Name = name
        return (await self._stub.UpdateSession(update, timeout=timeout))

    async def jobs(self, timeout=TIMEOUT) -> list[client_pb2.Job]:
        jobs: client_pb2.Jobs = await self._stub.GetJobs(common_pb2.Empty(), timeout=timeout)
        return list(jobs.Jobs)

    async def kill_job(self, job_id: int, timeout=TIMEOUT) -> client_pb2.KillJob:
        kill = client_pb2.KillJobReq()
        kill.ID = job_id
        return (await self._stub.KillJob(kill, timeout=timeout))

    async def start_mtls_listener(self, host: str, port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.MTLSListener:
        mtls = client_pb2.MTLSListenerReq()
        mtls.Host = host
        mtls.Port = port
        mtls.Persistent = persistent
        return (await self._stub.StartMTLSListener(mtls, timeout=timeout))

    async def start_wg_listener(self, port: int, tun_ip: str, n_port: int, key_port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.WGListener:
        wg = client_pb2.WGListenerReq()
        wg.Port = port
        wg.TunIP = tun_ip
        wg.NPort = n_port
        wg.KeyPort = key_port
        wg.Persistent = persistent
        return (await self._stub.StartWGListener(wg, timeout=timeout))

    async def start_dns_listener(self, domains: list[str], canaries: bool, host: str, port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.DNSListener:
        dns = client_pb2.DNSListenerReq()
        dns.Domains = domains
        dns.Canaries = canaries
        dns.Host = host
        dns.Port = port
        dns.Persistent = persistent
        return (await self._stub.StartDNSListener(dns, timeout=timeout))

    async def start_https_listener(self, domain: str, host: str, port: int, secure: bool, website: str, cert: bytes, key: bytes, acme: bool, persistent=False, timeout=TIMEOUT) -> client_pb2.HTTPListener:
        http = client_pb2.HTTPListenerReq()
        http.Domain = domain
        http.Host = host
        http.Port = port
        http.Secure = secure
        http.Website = website
        http.Cert = cert
        http.Key = key
        http.ACME = acme
        http.Persistent = persistent
        return (await self._stub.StartHTTPListener(http, timeout=timeout))

    async def start_http_listener(self, domain: str, host: str, port: int, secure: bool, website: str, persistent=False, timeout=TIMEOUT) -> client_pb2.HTTPListener:
        http = client_pb2.HTTPListenerReq()
        http.Domain = domain
        http.Host = host
        http.Port = port
        http.Secure = False
        http.Website = website
        http.ACME = False
        http.Persistent = persistent
        return (await self._stub.StartHTTPListener(http, timeout=timeout))

    async def start_tcp_stager_listener(self, protocol: client_pb2.StageProtocol, host: str, port: int, data: bytes, timeout=TIMEOUT) -> client_pb2.StagerListener:
        stage = client_pb2.StagerListenerReq()
        stage.Protocol = protocol
        stage.Host = host
        stage.Port = port
        stage.Data = data
        return (await self._stub.StartTCPStagerListener(stage, timeout=timeout))

    async def start_http_stager_listener(self, protocol: client_pb2.StageProtocol, host: str, port: int, data: bytes, cert: bytes, key: bytes, acme: bool, timeout=TIMEOUT) -> client_pb2.StagerListener:
        stage = client_pb2.StagerListenerReq()
        stage.Protocol = protocol
        stage.Host = host
        stage.Port = port
        stage.Data = data
        stage.Cert = cert
        stage.Key = key
        stage.ACME = acme
        return (await self._stub.StartHTTPStagerListener(stage, timeout=timeout))

    async def generate(self, config: client_pb2.ImplantConfig, timeout=360) -> client_pb2.Generate:
        req = client_pb2.GenerateReq()
        req.ImplantConfig = config
        return (await self._stub.Generate(req, timeout=timeout))

    async def regenerate(self, implant_name: str, timeout=TIMEOUT) -> client_pb2.Generate:
        regenerate = client_pb2.RegenerateReq()
        regenerate.ImpantName = implant_name
        return (await self._stub.Regenerate(regenerate, timeout=timeout))

    async def implant_builds(self, implant_name: str, timeout=TIMEOUT) -> None:
        delete = client_pb2.DeleteReq()
        delete.Name = implant_name
        await self._stub.DeleteImplantBuild(delete, timeout=timeout)
    
    async def canaries(self, timeout=TIMEOUT) -> list[client_pb2.DNSCanary]:
        canaries = await self._stub.Canaries(common_pb2.Empty(), timeout=timeout)
        return list(canaries.Canaries)
    
    async def generate_wg_client_config(self, timeout=TIMEOUT) -> client_pb2.WGClientConfig:
        return (await self._stub.GenerateWGClientConfig(common_pb2.Empty(), timeout=timeout))

    async def generate_unique_ip(self, timeout=TIMEOUT) -> client_pb2.UniqueWGIP:
        return (await self._stub.GenerateUniqueIP(common_pb2.Empty(), timeout=timeout))
    
    async def implant_profiles(self, timeout=TIMEOUT) -> list[client_pb2.ImplantProfile]:
        profiles = await self._stub.ImplantProfiles(common_pb2.Empty(), timeout=timeout)
        return list(profiles.Profiles)
    
    async def delete_implant_profile(self, profile_name, timeout=TIMEOUT) -> None:
        delete = client_pb2.DeleteReq()
        delete.Name = profile_name
        await self._stub.DeleteImplantProfile(delete, timeout=timeout)
    
    async def save_implant_profile(self, profile: client_pb2.ImplantProfile, timeout=TIMEOUT) -> client_pb2.ImplantProfile:
        return (await self._stub.SaveImplantProfile(profile, timeout=timeout))
    
    async def msf_stage(self, arch: str, format: str, host: str, port: int, os: str, protocol: client_pb2.StageProtocol, badchars=[], timeout=TIMEOUT) -> client_pb2.MsfStager:
        stagerReq = client_pb2.MsfStagerReq()
        stagerReq.Arch = arch
        stagerReq.Format = format
        stagerReq.Port = port
        stagerReq.Host = host
        stagerReq.OS = os
        stagerReq.Protocol = protocol
        stagerReq.BadChars = badchars
        return (await self._stub.MsfStage(stagerReq, timeout=timeout))

    async def shellcode_rdi(self, data: bytes, function_name: str, arguments: str, timeout=TIMEOUT) -> client_pb2.ShellcodeRDI:
        shellReq = client_pb2.ShellcodeRDIReq()
        shellReq.Data = data
        shellReq.FunctionName = function_name
        shellReq.Arguments = arguments
        return (await self._stub.ShellcodeRDI(shellReq, timeout=timeout))


class InteractiveSession(BaseSession):

    def ping(self) -> sliver_pb2.Ping:
        ping = sliver_pb2.Ping()
        ping.Request = self.request()
        return self._stub.Ping(ping, timeout=self.timeout)

    def ps(self) -> sliver_pb2.Ps:
        ps = sliver_pb2.PsReq()
        return self._stub.Ps(self.request(ps), timeout=self.timeout)
    
    def terminate(self, pid: int, force=False) -> sliver_pb2.Terminate:
        terminator = sliver_pb2.TerminateReq()
        terminator.Pid = pid
        terminator.Force = force
        return self._stub.Terminate(self.request(terminator), timeout=self.timeout)

    def ifconfig(self) -> sliver_pb2.Ifconfig:
        return self._stub.Ifconfig(self.request(sliver_pb2.IfconfigReq(), timeout=self.timeout))
    
    def netstat(self, tcp: bool, udp: bool, ipv4: bool, ipv6: bool, listening=True) -> list[sliver_pb2.SockTabEntry]:
        net = sliver_pb2.NetstatReq()
        net.TCP = tcp
        net.UDP = udp
        net.IP4 = ipv4
        net.IP6 = ipv6
        net.Listening = listening
        stat = self._stub.Netstat(self.request(net), timeout=self.timeout)
        return list(stat.Entries)
    
    def ls(self, remote_path: str) -> sliver_pb2.Ls:
        ls = sliver_pb2.LsReq()
        ls.Path = remote_path
        return self._stub.Ls(self.request(ls), timeout=self.timeout)

    def cd(self, remote_path: str) -> sliver_pb2.Pwd:
        cd = sliver_pb2.CdReq()
        cd.Path = remote_path
        return self._stub.Cd(self.request(cd), timeout=self.timeout)

    def pwd(self) -> sliver_pb2.Pwd:
        pwd = sliver_pb2.PwdReq()
        return self._stub.Pwd(self.request(pwd), timeout=self.timeout)

    def rm(self, remote_path: str, recursive=False, force=False) -> sliver_pb2.Rm:
        rm = sliver_pb2.RmReq()
        rm.Path = remote_path
        rm.Recursive = recursive
        rm.Force = force
        return self._stub.Rm(self.request(rm), timeout=self.timeout)

    def mkdir(self, remote_path: str) -> sliver_pb2.Mkdir:
        make = sliver_pb2.MkdirReq()
        make.Path = remote_path
        return self._stub.Mkdir(self.request(make), timeout=self.timeout)

    def download(self, remote_path: str) -> sliver_pb2.Download:
        download = sliver_pb2.DownloadReq()
        download.Path = remote_path
        return self._stub.Download(self.request(download), timeout=self.timeout)

    def upload(self, remote_path: str, data: bytes, encoder='') -> sliver_pb2.Upload:
        upload = sliver_pb2.UploadReq()
        upload.Path = remote_path
        upload.Data = data
        upload.Encoder = encoder
        return self._stub.Upload(self.request(upload), timeout=self.timeout)

    def process_dump(self, pid: int) -> sliver_pb2.ProcessDump:
        procdump = sliver_pb2.ProcessDumpReq()
        procdump.Pid = pid
        return self._stub.ProcessDump(self.request(procdump), timeout=self.timeout)

    def run_as(self, username: str, process_name: str, args: str) -> sliver_pb2.RunAs:
        run_as = sliver_pb2.RunAsReq()
        run_as.Username = username
        run_as.ProcessName = process_name
        run_as.Args = args
        return self._stub.RunAs(self.request(run_as), timeout=self.timeout)

    def impersonate(self, username: str) -> sliver_pb2.Impersonate:
        impersonate = sliver_pb2.ImpersonateReq()
        impersonate.Username = username
        return self._stub.Impersonate(self.request(impersonate), timeout=self.timeout)
    
    def revert_to_self(self) -> sliver_pb2.RevToSelf:
        return self._stub.RevToSelf(self.request(sliver_pb2.RevToSelfReq()), timeout=self.timeout)
    
    def get_system(self, hosting_process: str, config: client_pb2.ImplantConfig) -> sliver_pb2.GetSystem:
        system = client_pb2.GetSystemReq()
        system.HostingProcess = hosting_process
        system.Config = config
        return self._stub.GetSystem(self.request(system), timeout=self.timeout)
    
    def execute_shellcode(self, data: bytes, rwx: bool, pid: int, encoder='') -> sliver_pb2.Task:
        return self.task(data, rwx, pid, encoder)

    def task(self, data: bytes, rwx: bool, pid: int, encoder='') -> sliver_pb2.Task:
        task = sliver_pb2.TaskReq()
        task.Encoder = encoder
        task.RWXPages = rwx
        task.Pid = pid
        task.Data = data
        return self._stub.Task(self.request(task), timeout=self.timeout)
    
    def msf(self, payload: str, lhost: str, lport: int, encoder: str, iterations: int) -> None:
        msf = client_pb2.MSFReq()
        msf.Payload = payload
        msf.LHost = lhost
        msf.LPort = lport
        msf.Encoder = encoder
        msf.Iterations = iterations
        return self._stub.Msf(self.request(msf), timeout=self.timeout)

    def msf_remote(self, payload: str, lhost: str, lport: int, encoder: str, iterations: int, pid: int) -> None:
        msf = client_pb2.MSFRemoteReq()
        msf.Payload = payload
        msf.LHost = lhost
        msf.LPort = lport
        msf.Encoder = encoder
        msf.Iterations = iterations
        msf.PID = pid
        return self._stub.Msf(self.request(msf), timeout=self.timeout)
    
    def execute_assembly(self, assembly: bytes, arguments: str, process: str, is_dll: bool, arch: str, class_name: str, method: str, app_domain: str) -> sliver_pb2.ExecuteAssembly:
        asm = sliver_pb2.ExecuteAssemblyReq()
        asm.Assembly = assembly
        asm.Arguments = arguments
        asm.Process = process
        asm.IsDLL = is_dll
        asm.Arch = arch
        asm.ClassName = class_name
        asm.AppDomain = app_domain
        return self._stub.ExecuteAssembly(self.request(asm), timeout=self.timeout)
    
    def migrate(self, pid: int, config: client_pb2.ImplantConfig) -> sliver_pb2.Migrate:
        migrate = client_pb2.MigrateReq()
        migrate.Pid = pid
        migrate.Config = config
        return self._stub.Migrate(self.request(migrate), timeout=self.timeout)

    def execute(self, exe: str, args: list[str], output: bool) -> sliver_pb2.Execute:
        exec = sliver_pb2.ExecuteReq()
        exec.Path = exe
        exec.Args = args
        exec.Output = output
        return self._stub.Execute(self.request(exec), timeout=self.timeout)
    
    def execute_token(self, exe: str, args: list[str], output: bool) -> sliver_pb2.Execute:
        execToken = sliver_pb2.ExecuteTokenReq()
        execToken.Path = exe
        execToken.Args = args
        execToken.Output = output
        return self._stub.ExecuteToken(self.request(execToken), timeout=self.timeout)
    
    def sideload(self, data: bytes, process_name: str, arguments: str, entry_point: str, kill: bool) -> sliver_pb2.Sideload:
        side = sliver_pb2.SideloadReq()
        side.Data = data
        side.ProcessName = process_name
        side.Args = arguments
        side.EntryPoint = entry_point
        side.Kill = kill
        return self._stub.Sideload(self.request(side), timeout=self.timeout)
    
    def spawn_dll(self, data: bytes, process_name: str, arguments: str, entry_point: str, kill: bool) -> sliver_pb2.SpawnDll:
        spawn = sliver_pb2.InvokeSpawnDllReq()
        spawn.Data = data
        spawn.ProcessName = process_name
        spawn.Args = arguments
        spawn.EntryPoint = entry_point
        spawn.Kill = kill
        return self._stub.SpawnDll(self.request(spawn), timeout=self.timeout)
    
    def screenshot(self) -> sliver_pb2.Screenshot:
        return self._stub.Screenshot(self.request(sliver_pb2.ScreenshotReq()), timeout=self.timeout)
    
    def named_pipes(self, pipe_name: str) -> sliver_pb2.NamedPipes:
        pipe = sliver_pb2.NamedPipesReq()
        pipe.PipeName = pipe_name
        return self._stub.NamedPipes(self.request(pipe), timeout=self.timeout)

    def tcp_pivot_listener(self, address: str) -> sliver_pb2.TCPPivot:
        pivot = sliver_pb2.TCPPivotReq()
        pivot.Address = address
        return self._stub.TCPListener(self.request(pivot), timeout=self.timeout)
    
    def pivots(self) -> list[sliver_pb2.PivotEntry]:
        pivots = self._stub.ListPivots(self.request(sliver_pb2.PivotListReq()), timeout=self.timeout)
        return list(pivots.Entries)

    def start_service(self, name: str, description: str, exe: str, hostname: str, arguments: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StartServiceReq()
        svc.ServiceName = name
        svc.ServiceDescription = description
        svc.BinPath = exe
        svc.Hostname = hostname
        svc.Arguments = arguments
        return self._stub.StartService(self.request(svc), timeout=self.timeout)
    
    def stop_service(self, name: str, hostname: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StopServiceReq()
        svc.ServiceInfo.ServiceName = name
        svc.ServiceInfo.Hostname = hostname
        return self._stub.StopService(self.request(svc), timeout=self.timeout)

    def remove_service(self, name: str, hostname: str) -> sliver_pb2.ServiceInfo:
        svc = sliver_pb2.StopServiceReq()
        svc.ServiceInfo.ServiceName = name
        svc.ServiceInfo.Hostname = hostname
        return self._stub.RemoveService(self.request(svc), timeout=self.timeout)

    def make_token(self, username: str, password: str, domain: str) -> sliver_pb2.MakeToken:
        make = sliver_pb2.MakeTokenReq()
        make.Username = username
        make.Password = password
        make.Domain = domain
        return self._stub.MakeToken(self.request(make), timeout=self.timeout)

    def get_env(self, name: str) -> sliver_pb2.EnvInfo:
        env = sliver_pb2.EnvReq()
        env.Name = name
        return self._stub.GetEnv(self.request(env), timeout=self.timeout)
    
    def set_env(self, name: str, value: str) -> sliver_pb2.SetEnv:
        env = sliver_pb2.SetEnvReq()
        env.EnvVar.Key = name
        env.EnvVar.Value = value
        return self._stub.SetEnv(self.request(env), timeout=self.timeout)
    
    def backdoor(self, remote_path: str, profile_name: str) -> sliver_pb2.Backdoor:
        backdoor = sliver_pb2.BackdoorReq()
        backdoor.FilePath = remote_path
        backdoor.ProfileName = profile_name
        return self._stub.Backdoor(self.request(backdoor), timeout=self.timeout)
    
    def registry_read(self, hive: str, reg_path: str, key: str, hostname: str) -> sliver_pb2.RegistryRead:
        reg = sliver_pb2.RegistryReadReq()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        return self._stub.RegistryRead(self.request(reg), timeout=self.timeout)

    def registry_write(self, hive: str, reg_path: str, key: str, hostname: str, string_value: str, byte_value: bytes, dword_value: int, qword_value: int, reg_type: sliver_pb2.RegistryType) -> sliver_pb2.RegistryWrite:
        reg = sliver_pb2.RegistryWriteReq()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        reg.StringValue = string_value
        reg.ByteValue = byte_value
        reg.DWordValue = dword_value
        reg.QWordValue = qword_value
        reg.Type = reg_type
        return self._stub.RegistryWrite(self.request(reg), timeout=self.timeout)
    
    def registry_create_key(self, hive: str, reg_path: str, key: str, hostname: str) -> sliver_pb2.RegistryCreateKey:
        reg = sliver_pb2.RegistryCreateKey()
        reg.Hive = hive
        reg.Path = reg_path
        reg.Key = key
        reg.Hostname = hostname
        return self._stub.RegistryWrite(self.request(reg), timeout=self.timeout)


class SliverClient(BaseClient):

    ''' Client implementation '''

    def connect(self) -> None:
        self._channel = grpc.secure_channel(
            target=self.target,
            credentials=self.credentials,
            options=self.options,
        )
        self._stub = SliverRPCStub(self._channel)

    def interact(self, session_id: int, timeout=TIMEOUT) -> Union[InteractiveSession, None]:
        session = self.session_by_id(session_id, timeout)
        if session is not None:
            return InteractiveSession(session, self._channel)

    def session_by_id(self, session_id: int, timeout=TIMEOUT) -> Union[client_pb2.Session, None]:
        sessions = self.sessions(timeout)
        for session in sessions:
            if session.ID == session_id:
                return session
        return None
    
    def version(self, timeout=TIMEOUT) -> client_pb2.Version:
        return self._stub.GetVersion(common_pb2.Empty(), timeout=timeout)

    def operators(self, timeout=TIMEOUT) -> list[client_pb2.Operator]:
        operators = self._stub.GetOperators(common_pb2.Empty(), timeout=timeout)
        return list(operators.Operators)

    def sessions(self, timeout=TIMEOUT) -> list[client_pb2.Session]:
        sessions: client_pb2.Sessions = self._stub.GetSessions(common_pb2.Empty(), timeout=timeout)
        return list(sessions.Sessions)

    def update_session(self, session_id: int, name: str, timeout=TIMEOUT) -> client_pb2.Session:
        update = client_pb2.UpdateSession()
        update.SessionID = session_id
        update.Name = name
        return self._stub.UpdateSession(update, timeout=timeout)

    def kill_session(self, session_id: int, force=False, timeout=TIMEOUT) -> None:
        kill = sliver_pb2.KillSessionReq()
        kill.Request.SessionID = session_id
        kill.Request.Timeout = timeout-1
        kill.Force = force
        self._stub.KillSession(kill, timeout=timeout)

    def jobs(self, timeout=TIMEOUT) -> list[client_pb2.Job]:
        jobs: client_pb2.Jobs = self._stub.GetJobs(common_pb2.Empty(), timeout=timeout)
        return list(jobs.Jobs)

    def kill_job(self, job_id: int, timeout=TIMEOUT) -> client_pb2.KillJob:
        kill = client_pb2.KillJobReq()
        kill.ID = job_id
        return self._stub.KillJob(kill, timeout=timeout)

    def start_mtls_listener(self, host: str, port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.MTLSListener:
        mtls = client_pb2.MTLSListenerReq()
        mtls.Host = host
        mtls.Port = port
        mtls.Persistent = persistent
        return self._stub.StartMTLSListener(mtls, timeout=timeout)

    def start_wg_listener(self, port: int, tun_ip: str, n_port: int, key_port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.WGListener:
        wg = client_pb2.WGListenerReq()
        wg.Port = port
        wg.TunIP = tun_ip
        wg.NPort = n_port
        wg.KeyPort = key_port
        wg.Persistent = persistent
        return self._stub.StartWGListener(wg, timeout=timeout)

    def start_dns_listener(self, domains: list[str], canaries: bool, host: str, port: int, persistent=False, timeout=TIMEOUT) -> client_pb2.DNSListener:
        dns = client_pb2.DNSListenerReq()
        dns.Domains = domains
        dns.Canaries = canaries
        dns.Host = host
        dns.Port = port
        dns.Persistent = persistent
        return self._stub.StartDNSListener(dns, timeout=timeout)

    def start_https_listener(self, domain: str, host: str, port: int, secure: bool, website: str, cert: bytes, key: bytes, acme: bool, persistent=False, timeout=TIMEOUT) -> client_pb2.HTTPListener:
        http = client_pb2.HTTPListenerReq()
        http.Domain = domain
        http.Host = host
        http.Port = port
        http.Secure = secure
        http.Website = website
        http.Cert = cert
        http.Key = key
        http.ACME = acme
        http.Persistent = persistent
        return self._stub.StartHTTPListener(http, timeout=timeout)

    def start_http_listener(self, domain: str, host: str, port: int, secure: bool, website: str, persistent=False, timeout=TIMEOUT) -> client_pb2.HTTPListener:
        http = client_pb2.HTTPListenerReq()
        http.Domain = domain
        http.Host = host
        http.Port = port
        http.Secure = False
        http.Website = website
        http.ACME = False
        http.Persistent = persistent
        return self._stub.StartHTTPListener(http, timeout=timeout)

    def start_tcp_stager_listener(self, protocol: client_pb2.StageProtocol, host: str, port: int, data: bytes, timeout=TIMEOUT) -> client_pb2.StagerListener:
        stage = client_pb2.StagerListenerReq()
        stage.Protocol = protocol
        stage.Host = host
        stage.Port = port
        stage.Data = data
        return self._stub.StartTCPStagerListener(stage, timeout=timeout)

    def start_http_stager_listener(self, protocol: client_pb2.StageProtocol, host: str, port: int, data: bytes, cert: bytes, key: bytes, acme: bool, timeout=TIMEOUT) -> client_pb2.StagerListener:
        stage = client_pb2.StagerListenerReq()
        stage.Protocol = protocol
        stage.Host = host
        stage.Port = port
        stage.Data = data
        stage.Cert = cert
        stage.Key = key
        stage.ACME = acme
        return self._stub.StartHTTPStagerListener(stage, timeout=timeout)

    def generate(self, config: client_pb2.ImplantConfig, timeout=360) -> client_pb2.Generate:
        req = client_pb2.GenerateReq()
        req.ImplantConfig = config
        return self._stub.Generate(req, timeout=timeout)

    def regenerate(self, implant_name: str, timeout=TIMEOUT) -> client_pb2.Generate:
        regenerate = client_pb2.RegenerateReq()
        regenerate.ImpantName = implant_name
        return self._stub.Regenerate(regenerate, timeout=timeout)

    def implant_builds(self, implant_name: str, timeout=TIMEOUT) -> None:
        delete = client_pb2.DeleteReq()
        delete.Name = implant_name
        self._stub.DeleteImplantBuild(delete, timeout=timeout)
    
    def canaries(self, timeout=TIMEOUT) -> list[client_pb2.DNSCanary]:
        canaries = self._stub.Canaries(common_pb2.Empty(), timeout=timeout)
        return list(canaries.Canaries)
    
    def generate_wg_client_config(self, timeout=TIMEOUT) -> client_pb2.WGClientConfig:
        return self._stub.GenerateWGClientConfig(common_pb2.Empty(), timeout=timeout)

    def generate_unique_ip(self, timeout=TIMEOUT) -> client_pb2.UniqueWGIP:
        return self._stub.GenerateUniqueIP(common_pb2.Empty(), timeout=timeout)
    
    def implant_profiles(self, timeout=TIMEOUT) -> list[client_pb2.ImplantProfile]:
        profiles = self._stub.ImplantProfiles(common_pb2.Empty(), timeout=timeout)
        return list(profiles.Profiles)
    
    def delete_implant_profile(self, profile_name, timeout=TIMEOUT) -> None:
        delete = client_pb2.DeleteReq()
        delete.Name = profile_name
        self._stub.DeleteImplantProfile(delete, timeout=timeout)
    
    def save_implant_profile(self, profile: client_pb2.ImplantProfile, timeout=TIMEOUT) -> client_pb2.ImplantProfile:
        return self._stub.SaveImplantProfile(profile, timeout=timeout)
    
    def msf_stage(self, arch: str, format: str, host: str, port: int, os: str, protocol: client_pb2.StageProtocol, badchars=[], timeout=TIMEOUT) -> client_pb2.MsfStager:
        stagerReq = client_pb2.MsfStagerReq()
        stagerReq.Arch = arch
        stagerReq.Format = format
        stagerReq.Port = port
        stagerReq.Host = host
        stagerReq.OS = os
        stagerReq.Protocol = protocol
        stagerReq.BadChars = badchars
        return self._stub.MsfStage(stagerReq, timeout=timeout)

    def shellcode_rdi(self, data: bytes, function_name: str, arguments: str, timeout=TIMEOUT) -> client_pb2.ShellcodeRDI:
        shellReq = client_pb2.ShellcodeRDIReq()
        shellReq.Data = data
        shellReq.FunctionName = function_name
        shellReq.Arguments = arguments
        return self._stub.ShellcodeRDI(shellReq, timeout=timeout)