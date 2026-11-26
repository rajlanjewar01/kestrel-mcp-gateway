from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WmsStockLookupRequest(BaseModel):
    sku: str = Field(..., description="Stock keeping unit identifier")
    site: str = Field(..., description="Warehouse site code (e.g. SITE-01)")


class TmsDockScheduleRequest(BaseModel):
    site: str = Field(..., description="Warehouse site code")
    date_from: str = Field(..., description="Start date (YYYY-MM-DD)")
    date_to: str = Field(..., description="End date (YYYY-MM-DD)")


class TmsBookingLookupRequest(BaseModel):
    booking_ref: str = Field(..., description="Booking reference number")


class TmsBookingCreateRequest(BaseModel):
    site: str = Field(..., description="Warehouse site code")
    carrier: str = Field(..., description="Carrier name")
    window: str = Field(..., description="Requested dock window (ISO datetime)")
    load_ref: str = Field(..., description="Load reference identifier")


class TmsBookingCancelRequest(BaseModel):
    booking_ref: str = Field(..., description="Booking reference to cancel")
    reason: str = Field(..., description="Reason for cancellation")


class TicketSearchRequest(BaseModel):
    query: str = Field(..., description="Search terms (plain text, operators not permitted)")
    status: Optional[str] = Field(None, description="Filter by status: open, closed, or all")
    site: Optional[str] = Field(None, description="Filter by site code")


class TicketCreateRequest(BaseModel):
    site: str = Field(..., description="Site code where the exception occurred")
    category: str = Field(..., description="Ticket category")
    summary: str = Field(..., max_length=200, description="Brief summary of the issue")
    detail: str = Field(..., max_length=2000, description="Detailed description")


class TicketCommentRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket identifier")
    body: str = Field(..., max_length=2000, description="Comment text")


class TicketCloseRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket identifier")
    resolution: str = Field(..., max_length=500, description="Resolution summary")


class ContractLookupRequest(BaseModel):
    customer_id: str = Field(..., description="Customer account identifier")


class RateCardLookupRequest(BaseModel):
    customer_id: str = Field(..., description="Customer account identifier")
