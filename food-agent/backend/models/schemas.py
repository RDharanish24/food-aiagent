from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class CartItem(BaseModel):
    itemName: str
    quantity: int = 1
    customizations: List[str] = Field(default_factory=list)
    price: Optional[str] = None
    itemId: str

class OrderStateItem(BaseModel):
    name: str
    quantity: int = 1
    customizations: List[str] = Field(default_factory=list)

class OrderState(BaseModel):
    intent: Optional[str] = None
    restaurant_preference: Optional[str] = None
    items: List[OrderStateItem] = Field(default_factory=list)
    delivery_address_tag: Optional[str] = None
    is_complete: bool = False

class DeliveryDetails(BaseModel):
    address: str
    time: str

class SessionDoc(BaseModel):
    sessionId: str
    status: str = "active"
    cart: List[CartItem] = Field(default_factory=list)
    deliveryDetails: Optional[DeliveryDetails] = None
    latestScreenData: Any = None
    orderState: OrderState = Field(default_factory=OrderState)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class MessageDoc(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ConversationDoc(BaseModel):
    sessionId: str
    messages: List[MessageDoc] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class OrderLogDoc(BaseModel):
    sessionId: str
    items: List[CartItem] = Field(default_factory=list)
    status: str
    agentActions: List[Any] = Field(default_factory=list)
    placedAt: datetime = Field(default_factory=datetime.utcnow)

# Request / Response Schemas
class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None

class LoginPhoneRequest(BaseModel):
    sessionId: str
    phone: str

class LoginOtpRequest(BaseModel):
    sessionId: str
    otp: str

class NavigateRequest(BaseModel):
    sessionId: str
    url: str

class ResetOrderRequest(BaseModel):
    sessionId: str
