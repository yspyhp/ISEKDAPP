import { NextRequest, NextResponse } from 'next/server';

// Proxy to Python backend
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:5001';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('sessionId');
    
    if (!sessionId) {
      return NextResponse.json(
        { error: 'sessionId is required' },
        { status: 400 }
      );
    }
    
    // Forward GET request to Python backend
    const response = await fetch(`${PYTHON_BACKEND_URL}/api/chat?sessionId=${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.error || 'Backend error' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Chat API GET error:', error);
    
    // Provide more detailed error information
    let errorMessage = 'Internal server error';
    if (error instanceof SyntaxError) {
      errorMessage = 'Invalid JSON format';
    } else if (error instanceof TypeError) {
      errorMessage = 'Type error in request processing';
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return NextResponse.json(
      { error: errorMessage, details: error instanceof Error ? error.stack : undefined },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    // Log request details for debugging
    const requestContentType = request.headers.get('content-type');
    console.log('🔧 Request content-type:', requestContentType);
    
    // Check if request has a body
    const contentLength = request.headers.get('content-length');
    console.log('🔧 Request content-length:', contentLength);
    
    let body;
    try {
      body = await request.json();
    } catch (jsonError) {
      console.error('🔧 JSON parse error:', jsonError);
      
      return NextResponse.json(
        { 
          error: 'Invalid JSON format in request body',
          details: jsonError instanceof Error ? jsonError.message : 'Unknown JSON error'
        },
        { status: 400 }
      );
    }

    // Extract session information from the request
    const { sessionId, agentId, messages, system } = body;
    
    console.log('🔧 Frontend API received:', { sessionId, agentId, messagesCount: messages?.length });
    
    // Normalize message content to ensure it's always a string
    const normalizedMessages = messages?.map((msg: any) => {
      let content = msg.content;
      if (Array.isArray(content)) {
        // If content is an array of objects with text fields
        if (content.length > 0 && typeof content[0] === 'object' && 'text' in content[0]) {
          content = content.map((c: any) => c.text).join('');
        } else {
          content = content.join('');
        }
      } else if (typeof content !== 'string') {
        content = String(content);
      }
      return { ...msg, content };
    }) || [];
    
    // If agentId is not provided in the request body, try to get it from the session
    let finalAgentId = agentId;
    if (!finalAgentId && sessionId) {
      try {
        // Get session info from backend
        const sessionResponse = await fetch(`${PYTHON_BACKEND_URL}/api/sessions`, {
          method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

        if (sessionResponse.ok) {
          const sessions = await sessionResponse.json();
          const session = sessions.find((s: any) => s.id === sessionId);
          if (session) {
            finalAgentId = session.agentId;
            console.log('🔧 Retrieved agentId from session:', finalAgentId);
          }
      }
    } catch (error) {
        console.error('Failed to get session info:', error);
      }
    }
    
    if (!finalAgentId) {
      return NextResponse.json(
        { error: 'agentId is required' },
        { status: 400 }
      );
    }

    // Prepare the request for the Python backend
    const backendRequest = {
      agentId: finalAgentId,
      sessionId,
      messages: normalizedMessages,
      system
    };
    
    console.log('🔧 Sending to backend:', backendRequest);
    
    // Forward request to Python backend
    const response = await fetch(`${PYTHON_BACKEND_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': request.headers.get('Accept') || 'application/json',
      },
      body: JSON.stringify(backendRequest),
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('🔧 Backend error:', error);
      return NextResponse.json(
        { error: error.error || 'Backend error' },
        { status: response.status }
      );
    }

    // Check if backend returned streaming response
    const contentType = response.headers.get('content-type');
    const dataStreamHeader = response.headers.get('x-vercel-ai-data-stream');
    console.log('🔧 Backend response content-type:', contentType);
    console.log('🔧 Backend response x-vercel-ai-data-stream:', dataStreamHeader);
    
    if (contentType && (contentType.includes('text/event-stream') || contentType.includes('text/plain')) && dataStreamHeader) {
      // Return streaming response for assistant-stream format
      const stream = response.body;
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'x-vercel-ai-data-stream': 'v1',
        },
      });
    } else {
      // Only parse as JSON if not streaming
      const data = await response.json();
      return NextResponse.json(data);
    }
  } catch (error) {
    console.error('Chat API POST error:', error);
    
    // Provide more detailed error information
    let errorMessage = 'Internal server error';
    if (error instanceof SyntaxError) {
      errorMessage = 'Invalid JSON format';
    } else if (error instanceof TypeError) {
      errorMessage = 'Type error in request processing';
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return NextResponse.json(
      { error: errorMessage, details: error instanceof Error ? error.stack : undefined },
      { status: 500 }
    );
  }
}
