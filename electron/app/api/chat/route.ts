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
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Extract session information from the request
    const { sessionId, agentId, messages, system } = body;
    
    console.log('🔧 Frontend API received:', { sessionId, agentId, messagesCount: messages?.length });
    
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
      messages,
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
    console.log('🔧 Backend response content-type:', contentType);
    
    if (contentType && contentType.includes('text/event-stream')) {
      // Return streaming response
      const stream = response.body;
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } else {
      // Only parse as JSON if not SSE
      const data = await response.json();
      return NextResponse.json(data);
    }
  } catch (error) {
    console.error('Chat API POST error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
