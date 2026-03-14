"""Connection manager for WebSocket discovery chat."""
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ActiveConnection:
    """Represents an active WebSocket connection."""
    
    def __init__(
        self,
        client_id: str,
        project_id: str,
        websocket: WebSocket,
        display_name: Optional[str] = None
    ):
        self.client_id = client_id
        self.project_id = project_id
        self.websocket = websocket
        self.display_name = display_name
        self.connected_at = datetime.utcnow()
        self.current_run_id: Optional[str] = None
    
    async def send(self, event: Dict) -> None:
        """Send an event to this connection."""
        await self.websocket.send_json(event)
    
    def __repr__(self):
        return f"ActiveConnection(client_id={self.client_id}, project_id={self.project_id})"


class ConnectionManager:
    """Manages active WebSocket connections.
    
    Ensures only one active connection per project_id (ChatGPT-style: one tab only).
    """
    
    def __init__(self):
        self._connections: Dict[str, ActiveConnection] = {}
        self._project_to_client: Dict[str, str] = {}
    
    async def connect(
        self,
        client_id: str,
        project_id: str,
        websocket: WebSocket,
        display_name: Optional[str] = None
    ) -> ActiveConnection:
        """Register a new connection.
        
        Raises:
            ValueError: If a connection already exists for this project_id
        """
        if project_id in self._project_to_client:
            existing_client_id = self._project_to_client[project_id]
            raise ValueError(
                f"CONNECTION_EXISTS: Another connection is already active for project {project_id}. "
                f"Existing client: {existing_client_id}"
            )
        
        connection = ActiveConnection(client_id, project_id, websocket, display_name)
        self._connections[client_id] = connection
        self._project_to_client[project_id] = client_id
        
        logger.info(f"Client {client_id} connected to project {project_id}")
        
        return connection
    
    async def disconnect(self, client_id: str) -> None:
        """Remove a connection."""
        connection = self._connections.pop(client_id, None)
        
        if connection:
            project_id = connection.project_id
            if self._project_to_client.get(project_id) == client_id:
                self._project_to_client.pop(project_id, None)
            
            logger.info(f"Client {client_id} disconnected from project {project_id}")
    
    async def send(self, client_id: str, event: Dict) -> bool:
        """Send an event to a specific client.
        
        Returns:
            True if sent successfully, False if client not found
        """
        connection = self._connections.get(client_id)
        if not connection:
            return False
        
        try:
            await connection.send(event)
            return True
        except Exception as e:
            logger.error(f"Failed to send to client {client_id}: {e}")
            await self.disconnect(client_id)
            return False
    
    def get_connection(self, client_id: str) -> Optional[ActiveConnection]:
        """Get a connection by client_id."""
        return self._connections.get(client_id)
    
    def get_by_project(self, project_id: str) -> Optional[ActiveConnection]:
        """Get the active connection for a project."""
        client_id = self._project_to_client.get(project_id)
        if client_id:
            return self._connections.get(client_id)
        return None
    
    def set_run_id(self, client_id: str, run_id: Optional[str]) -> None:
        """Set the current run_id for a client."""
        connection = self._connections.get(client_id)
        if connection:
            connection.current_run_id = run_id
    
    def cancel_run(self, run_id: str) -> Optional[str]:
        """Cancel a running assistant response.
        
        Returns:
            client_id if a running response was cancelled, None otherwise
        """
        for client_id, connection in self._connections.items():
            if connection.current_run_id == run_id:
                connection.current_run_id = None
                logger.info(f"Cancelled run {run_id} for client {client_id}")
                return client_id
        return None
    
    def is_connected(self, project_id: str) -> bool:
        """Check if a project has an active connection."""
        return project_id in self._project_to_client
    
    def get_client_id(self, project_id: str) -> Optional[str]:
        """Get the client_id for an active project connection."""
        return self._project_to_client.get(project_id)
    
    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)


connection_manager = ConnectionManager()
