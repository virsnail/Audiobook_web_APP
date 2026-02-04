import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models.user import InvitationCode
from app.routers.auth import generate_invitation_code

async def main():
    print("🚀 Generating Invitation Code...")
    
    async with AsyncSessionLocal() as session:
        try:
            codes_generated = []
            for _ in range(20):
                code_str = generate_invitation_code()
                invitation = InvitationCode(
                    code=code_str,
                    created_by=None, # System created
                    expires_at=datetime.utcnow() + timedelta(days=365), # Long expiry
                    max_uses=10
                )
                session.add(invitation)
                codes_generated.append(code_str)
            
            await session.commit()
            print(f"\n✅ {len(codes_generated)} Invitation Codes Created Successfully:")
            print("-" * 40)
            for i, c in enumerate(codes_generated, 1):
                print(f"{i:02d}. {c}")
            print("-" * 40)
            print(f"Each valid for 10 uses, expires in 365 days.")
        except Exception as e:
            print(f"❌ Error creating code: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(main())
