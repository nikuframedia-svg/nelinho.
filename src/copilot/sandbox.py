"""
ProdPlan ONE - Copilot Sandbox Isolation
=========================================

Sandbox executor using nested transactions (savepoints) for isolation.
Allows testing actions without committing changes.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SandboxExecutor:
    """
    Execute code in sandbox with automatic rollback.
    
    Uses SQLAlchemy nested transactions (savepoints) to isolate execution.
    All changes are automatically rolled back when exiting the context.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @asynccontextmanager
    async def execute_in_sandbox(
        self,
        query_func: Callable[[], Any],
    ) -> AsyncGenerator[Any, None]:
        """
        Execute function in sandbox (nested transaction).
        
        Creates a savepoint, executes the function, and automatically
        rolls back when exiting the context.
        
        Usage:
            sandbox = SandboxExecutor(session)
            async with sandbox.execute_in_sandbox(lambda: do_something()):
                result = await do_something()
                # All changes will be rolled back automatically
        """
        # Create savepoint (nested transaction)
        nested = await self.session.begin_nested()
        
        try:
            logger.debug("Sandbox execution started (savepoint created)")
            
            # Execute the function
            result = await query_func()
            
            # Yield result (but don't commit - will rollback on exit)
            yield result
        
        except Exception as e:
            # Rollback on error
            await nested.rollback()
            logger.error(f"Sandbox execution failed, rolled back: {e}")
            raise
        
        finally:
            # Always rollback when exiting context
            await nested.rollback()
            logger.debug("Sandbox execution completed, rolled back")

