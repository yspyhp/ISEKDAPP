import { NextRequest, NextResponse } from 'next/server';

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Session ID is required' }, { status: 400 });
  }
  try {
    const response = await fetch(`http://localhost:5001/api/sessions/${id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json({ error: data.error || 'Failed to delete session' }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error proxying DELETE to backend:', error);
    return NextResponse.json({ error: 'Failed to delete session' }, { status: 500 });
  }
}
