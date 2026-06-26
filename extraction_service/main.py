"""FastAPI application for extraction service."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import (
    init_db,
    get_db,
    list_requirements,
    count_requirements,
    get_requirement_by_update_id,
    check_db_health,
)
from taxonomy import load_taxonomy

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic models for API

class RequirementResponse(BaseModel):
    """Response model for a single requirement."""
    update_id: str
    published_date: str
    source: str
    source_url: str
    celex: Optional[str]
    consolidation_date: Optional[str]
    access_timestamp: str
    regulation_family: str
    reference: Optional[str]
    title: str
    summary: Optional[str]
    change_type: str
    effective_date: Optional[str]
    deadline_date: Optional[str]
    severity: str
    action_required: Optional[str]
    scope: dict
    corrects: Optional[str]


class RequirementsListResponse(BaseModel):
    """Response model for list of requirements."""
    total: int
    limit: int
    offset: int
    requirements: list[RequirementResponse]


class ExtractionJobRequest(BaseModel):
    """Request model for triggering extraction job."""
    force_full_scan: bool = Field(
        default=False,
        description="Force full scan instead of incremental"
    )


class ExtractionJobResponse(BaseModel):
    """Response model for extraction job."""
    job_id: int
    status: str
    message: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    database: str
    taxonomy: str
    timestamp: str


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting extraction service...")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Load taxonomy
    try:
        load_taxonomy()
        logger.info("Taxonomy loaded")
    except Exception as e:
        logger.error(f"Failed to load taxonomy: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down extraction service...")


# Create FastAPI app
app = FastAPI(
    title="Extraction Service",
    description="Pull live regulatory requirements from EUR-Lex/CELLAR and ECHA",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all requests."""
    start_time = datetime.now(timezone.utc)
    
    response = await call_next(request)
    
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
    )
    
    return response


# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "Extraction Service",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    # Check database
    db_status = "healthy" if check_db_health(db) else "unhealthy"
    
    # Check taxonomy
    try:
        from taxonomy import get_taxonomy
        taxonomy = get_taxonomy()
        taxonomy_status = "loaded" if taxonomy._loaded else "not loaded"
    except Exception:
        taxonomy_status = "error"
    
    overall_status = "healthy" if db_status == "healthy" and taxonomy_status == "loaded" else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        database=db_status,
        taxonomy=taxonomy_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/requirements", response_model=RequirementsListResponse, tags=["Requirements"])
async def get_requirements(
    regulation_family: Optional[str] = Query(None, description="Filter by regulation family"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """
    List requirements with optional filters and pagination.
    
    Returns requirements sorted by deadline_date (earliest first).
    """
    try:
        # Get total count
        total = count_requirements(db, regulation_family, severity)
        
        # Get requirements
        requirements = list_requirements(db, regulation_family, severity, limit, offset)
        
        # Convert to response models
        requirement_responses = [
            RequirementResponse(**req.to_dict())
            for req in requirements
        ]
        
        return RequirementsListResponse(
            total=total,
            limit=limit,
            offset=offset,
            requirements=requirement_responses,
        )
    except Exception as e:
        logger.error(f"Error listing requirements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/requirements/{update_id}", response_model=RequirementResponse, tags=["Requirements"])
async def get_requirement(
    update_id: str,
    db: Session = Depends(get_db),
):
    """Get a single requirement by update_id."""
    try:
        requirement = get_requirement_by_update_id(db, update_id)
        
        if not requirement:
            raise HTTPException(status_code=404, detail=f"Requirement {update_id} not found")
        
        return RequirementResponse(**requirement.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting requirement {update_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract", response_model=ExtractionJobResponse, tags=["Extraction"])
async def trigger_extraction(
    request: ExtractionJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger an extraction job.
    
    The job runs in the background and extracts requirements from CELLAR and ECHA.
    """
    try:
        from database import start_extraction_run
        
        # Start extraction run
        run = start_extraction_run(db)
        
        # Add background task
        background_tasks.add_task(
            run_extraction_job,
            run.id,
            request.force_full_scan,
        )
        
        logger.info(f"Started extraction job {run.id}")
        
        return ExtractionJobResponse(
            job_id=run.id,
            status="running",
            message=f"Extraction job {run.id} started in background",
        )
    except Exception as e:
        logger.error(f"Error starting extraction job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task for extraction job

async def run_extraction_job(run_id: int, force_full_scan: bool):
    """
    Run extraction job in background.
    
    This is the main extraction pipeline:
    1. Discover documents from CELLAR SPARQL
    2. Fetch Formex XML for each document
    3. Parse and normalize to Requirement
    4. Deduplicate and persist to database
    5. Fetch ECHA SVHC list and create requirements
    """
    from database import (
        get_db_session,
        complete_extraction_run,
        fail_extraction_run,
        insert_requirement,
        update_requirement,
    )
    from clients import CellarClient, EchaClient
    from normalize import FormexParser, RequirementBuilder
    from change import ContentHasher, CursorTracker, ChangeDetector, deduplicate_requirements
    
    db = get_db_session()
    
    try:
        logger.info(f"Running extraction job {run_id}")
        
        # Initialize components
        cellar_client = CellarClient()
        echa_client = EchaClient()
        formex_parser = FormexParser()
        requirement_builder = RequirementBuilder()
        content_hasher = ContentHasher()
        cursor_tracker = CursorTracker(db)
        change_detector = ChangeDetector(db)
        
        requirements_found = 0
        requirements_new = 0
        requirements_updated = 0
        
        # Get cursor for incremental fetching
        cursor = None if force_full_scan else cursor_tracker.get_last_cursor()
        if cursor:
            logger.info(f"Using cursor: {cursor.isoformat()}")
        else:
            logger.info("Full scan (no cursor)")
        
        # CELLAR pipeline
        if settings.enable_cellar_sparql:
            logger.info("Starting CELLAR discovery...")
            documents = cellar_client.discover_documents(cursor)
            logger.info(f"Discovered {len(documents)} documents")
            
            for doc in documents:
                try:
                    celex = doc["celex"]
                    logger.info(f"Processing {celex}...")
                    
                    # Fetch Formex XML
                    result = cellar_client.fetch_formex_xml(celex)
                    if result is None:
                        logger.info(f"Skipping {celex} (not modified)")
                        continue
                    
                    xml_content, cache_headers = result
                    
                    # Parse Formex XML
                    parsed_metadata = formex_parser.parse(xml_content, celex)
                    
                    # Build source URL
                    source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
                    
                    # Build Requirement
                    requirement_data = requirement_builder.build(
                        parsed_metadata,
                        source_url,
                        datetime.now(timezone.utc),
                    )
                    
                    # Calculate content hash
                    content_hash = content_hasher.calculate_hash(requirement_data)
                    
                    # Detect change
                    change_type, existing_id = change_detector.detect_change(
                        requirement_data,
                        content_hash,
                    )
                    
                    requirements_found += 1
                    
                    if change_type == "new":
                        insert_requirement(db, requirement_data, content_hash)
                        requirements_new += 1
                        logger.info(f"Inserted new requirement: {celex}")
                    elif change_type == "changed":
                        update_requirement(db, existing_id, requirement_data, content_hash)
                        requirements_updated += 1
                        logger.info(f"Updated requirement: {celex}")
                    else:
                        logger.info(f"Requirement unchanged: {celex}")
                    
                except Exception as e:
                    logger.error(f"Error processing {celex}: {e}")
                    continue
            
            # Update cursor
            new_cursor = cursor_tracker.get_cursor_for_batch(documents)
            if new_cursor:
                cursor_tracker.advance_cursor(new_cursor)
        
        # ECHA pipeline
        if settings.enable_echa_fetch:
            logger.info("Starting ECHA fetch...")
            try:
                substances = echa_client.fetch_candidate_list()
                logger.info(f"Fetched {len(substances)} substances from ECHA")
                
                # TODO: Convert ECHA substances to Requirements
                # For MVP, we'll skip this and focus on CELLAR
                
            except Exception as e:
                logger.error(f"Error fetching ECHA: {e}")
        
        # Complete extraction run
        complete_extraction_run(
            db,
            run_id,
            requirements_found,
            requirements_new,
            requirements_updated,
            new_cursor if 'new_cursor' in locals() else None,
        )
        
        logger.info(
            f"Extraction job {run_id} completed: "
            f"{requirements_found} found, {requirements_new} new, {requirements_updated} updated"
        )
        
    except Exception as e:
        logger.error(f"Extraction job {run_id} failed: {e}")
        fail_extraction_run(db, run_id, str(e))
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
