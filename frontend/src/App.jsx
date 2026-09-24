import React, { useState } from 'react';
import './App.css';

function App() {
  const [requirement, setRequirement] = useState('Verify that a user can log in with valid credentials');
  const [runId, setRunId] = useState('');
  const [workflowStatus, setWorkflowStatus] = useState('');
  const [executionStatus, setExecutionStatus] = useState('');
  const [failureDetected, setFailureDetected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [testCase, setTestCase] = useState(null);
  const [generatedTestCode, setGeneratedTestCode] = useState('');
  const [executionResult, setExecutionResult] = useState(null);
  const [retrievedKnowledge, setRetrievedKnowledge] = useState(null);
  const [failureAnalysis, setFailureAnalysis] = useState(null);
  const [verificationResult, setVerificationResult] = useState(null);
  const [bugReport, setBugReport] = useState(null);
  const [regressionTest, setRegressionTest] = useState(null);
  const [approvalResponse, setApprovalResponse] = useState(null);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [error, setError] = useState('');

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
  const WORKFLOW_RUN_TOKEN = import.meta.env.VITE_WORKFLOW_RUN_TOKEN;

  const handleRunTest = async () => {
    setError('');
    setLoading(true);
    // Reset previous results
    setRunId('');
    setWorkflowStatus('');
    setExecutionStatus('');
    setFailureDetected(false);
    setApprovalRequired(false);
    setTestCase(null);
    setGeneratedTestCode('');
    setExecutionResult(null);
    setRetrievedKnowledge(null);
    setFailureAnalysis(null);
    setVerificationResult(null);
    setBugReport(null);
    setRegressionTest(null);
    setApprovalResponse(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/test/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${WORKFLOW_RUN_TOKEN}`
        },
        body: JSON.stringify({ requirement })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setRunId(data.run_id);
      setWorkflowStatus(data.workflow_status);
      setExecutionStatus(data.execution_status);
      setFailureDetected(data.failure_detected);
      setApprovalRequired(data.human_approval_required);
      setTestCase(data.test_case);
      setGeneratedTestCode(data.generated_test_code || '');
      setExecutionResult(data.execution_result);
      setRetrievedKnowledge(data.retrieved_knowledge);
      setFailureAnalysis(data.failure_analysis);
      setVerificationResult(data.verification_result);
      setBugReport(data.bug_report);
      setRegressionTest(data.regression_test);
    } catch (err) {
      setError(err.message || 'An unknown error occurred');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approved) => {
    if (!runId) return;
    setApprovalLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/test/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${WORKFLOW_RUN_TOKEN}`
        },
        body: JSON.stringify({ run_id: runId, approved })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setApprovalResponse(data);
    } catch (err) {
      setError(err.message || 'An unknown error occurred');
      console.error(err);
    } finally {
      setApprovalLoading(false);
    }
  };

  // Helper to render JSON or a message if null
  const renderContent = (content, emptyMessage = 'Not required for successful execution') => {
    if (content === null || content === undefined) {
      return <span className="null-text">{emptyMessage}</span>;
    }
    if (typeof content === 'string') {
      return <span>{content}</span>;
    }
    // For objects, we'll format as JSON with syntax highlighting (simple)
    return (
      <pre className="json-block">{JSON.stringify(content, null, 2)}</pre>
    );
  };

  // Helper to get status icon
  const getStatusIcon = (status) => {
    if (status === 'completed' || status === 'pass') return '✓';
    if (status === 'failed' || status === 'fail') return '✗';
    return '○';
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Agentic AI Software Testing Platform</h1>
        <p>Autonomous Test Generation, Execution, Failure Investigation and Regression Testing</p>
      </header>

      <main>
        <section className="requirement-section">
          <h2>Requirement Input</h2>
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="Enter software requirement..."
            rows={4}
          />
          <button
            onClick={handleRunTest}
            disabled={loading}
          >
            {loading ? 'Running...' : 'Run Test'}
          </button>
          {error && <p className="error">Error: {error}</p>}
        </section>

        {!runId ? (
          <p>Enter a requirement and click "Run Test" to start the workflow.</p>
        ) : (
          <>
            <section className="workflow-summary">
              <h2>Workflow Summary</h2>
              <div className="summary-grid">
                <div>
                  <strong>Run ID:</strong> {runId}
                </div>
                <div>
                  <strong>Workflow Status:</strong> {workflowStatus}
                </div>
                <div>
                  <strong>Execution Status:</strong> {executionStatus}
                </div>
                <div>
                  <strong>Failure Detected:</strong> {failureDetected ? 'Yes' : 'No'}
                </div>
              </div>
            </section>

            <section className="workflow-stages">
              <h2>Workflow Stages</h2>
              <div className="stages-flow">
                <div className="stage">
                  <div className="stage-icon">{getStatusIcon(workflowStatus === 'pass' || workflowStatus === 'completed' ? 'completed' : workflowStatus === 'fail' ? 'failed' : 'pending')}</div>
                  <div className="stage-label">Requirement</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{testCase ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                  <div className="stage-label">Test Case Generation</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{generatedTestCode ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                  <div className="stage-label">Selenium Test Generation</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{executionResult ? getStatusIcon(executionStatus === 'pass' ? 'completed' : executionStatus === 'fail' ? 'failed' : 'pending') : getStatusIcon('pending')}</div>
                  <div className="stage-label">Test Execution</div>
                </div>
                {failureDetected && (
                  <>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{retrievedKnowledge ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Knowledge Retrieval</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{failureAnalysis ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Failure Investigation</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{verificationResult ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Verification</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{bugReport ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Bug Report</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{regressionTest ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Regression Test</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{approvalRequired ? (approvalResponse ? getStatusIcon('completed') : getStatusIcon('pending')) : getStatusIcon('not-required')}</div>
                      <div className="stage-label">Human Approval</div>
                    </div>
                  </>
                )}
              </div>
            </section>

            {testCase && (
              <section className="result-section">
                <h2>Generated Test Case</h2>
                {renderContent(testCase)}
              </section>
            )}

            {generatedTestCode && (
              <section className="result-section">
                <h2>Generated Selenium Code</h2>
                <pre className="code-block">{generatedTestCode}</pre>
              </section>
            )}

            {executionResult && (
              <section className="result-section">
                <h2>Execution Result</h2>
                {renderContent(executionResult)}
              </section>
            )}

            {failureDetected && retrievedKnowledge && (
              <section className="result-section">
                <h2>Retrieved Knowledge</h2>
                {renderContent(retrievedKnowledge)}
              </section>
            )}

            {failureDetected && failureAnalysis && (
              <section className="result-section">
                <h2>Failure Analysis</h2>
                {renderContent(failureAnalysis)}
              </section>
            )}

            {failureDetected && verificationResult && (
              <section className="result-section">
                <h2>Verification Result</h2>
                {renderContent(verificationResult)}
              </section>
            )}

            {failureDetected && bugReport && (
              <section className="result-section">
                <h2>Bug Report</h2>
                {renderContent(bugReport)}
              </section>
            )}

            {failureDetected && regressionTest && (
              <section className="result-section">
                <h2>Regression Test</h2>
                {renderContent(regressionTest)}
              </section>
            )}

            {approvalRequired && (
              <section className="approval-section">
                <h2>Human Approval</h2>
                <p>Human approval is required for the bug report and regression test.</p>
                <div className="approval-buttons">
                  <button
                    onClick={() => handleApprove(true)}
                    disabled={approvalLoading}
                  >
                    {approvalLoading ? 'Approving...' : 'Approve'}
                  </button>
                  <button
                    onClick={() => handleApprove(false)}
                    disabled={approvalLoading}
                    className="reject"
                  >
                    {approvalLoading ? 'Rejecting...' : 'Reject'}
                  </button>
                </div>
                {approvalResponse && (
                  <div className="approval-response">
                    <p>Approval recorded: {approvalResponse.approved ? 'Approved' : 'Rejected'}</p>
                    <p>Bug report approved: {approvalResponse.bug_report_approved ? 'Yes' : 'No'}</p>
                    <p>Regression test approved: {approvalResponse.regression_test_approved ? 'Yes' : 'No'}</p>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;