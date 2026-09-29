import React, { useState } from 'react';
import './App.css';

function App() {
  const [requirement, setRequirement] = useState('Verify that a user can log in with valid credentials');
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:8001');
  const [sutId, setSutId] = useState('');
  const [sutContext, setSutContext] = useState('');
  const [testData, setTestData] = useState('');
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

  // Plural state for Phase 1-10 outputs
  const [testScenarios, setTestScenarios] = useState([]);
  const [testCases, setTestCases] = useState([]);
  const [executionResults, setExecutionResults] = useState([]);
  const [executionSummary, setExecutionSummary] = useState(null);
  const [failureAnalyses, setFailureAnalyses] = useState([]);
  const [verificationResults, setVerificationResults] = useState([]);
  const [bugReports, setBugReports] = useState([]);
  const [regressionTests, setRegressionTests] = useState([]);
  const [regressionExecutionResult, setRegressionExecutionResult] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
  const WORKFLOW_RUN_TOKEN = import.meta.env.VITE_WORKFLOW_RUN_TOKEN;

  // Helper to parse JSON safely
  const parseJson = (text) => {
    if (text.trim() === '') {
      return {};
    }
    try {
      return JSON.parse(text);
    } catch (err) {
      throw new Error(`Invalid JSON: ${err.message}`);
    }
  };

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
    // Reset plural state
    setTestScenarios([]);
    setTestCases([]);
    setExecutionResults([]);
    setExecutionSummary(null);
    setFailureAnalyses([]);
    setVerificationResults([]);
    setBugReports([]);
    setRegressionTests([]);
    setRegressionExecutionResult(null);

    try {
      const parsedSutContext = parseJson(sutContext);
      const parsedTestData = parseJson(testData);

      const response = await fetch(`${API_BASE_URL}/api/v1/test/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${WORKFLOW_RUN_TOKEN}`
        },
        body: JSON.stringify({
          requirement,
          base_url: baseUrl,
          sut_id: sutId || null,
          sut_context: parsedSutContext,
          test_data: parsedTestData
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Map singular fields (backward compatibility)
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
      setApprovalResponse(data.approval_response);

      // Map plural fields (Phase 1-10)
      setTestScenarios(data.test_scenarios || []);
      setTestCases(data.test_cases || []);
      setExecutionResults(data.execution_results || []);
      setExecutionSummary(data.execution_summary || null);
      setFailureAnalyses(data.failure_analyses || []);
      setVerificationResults(data.verification_results || []);
      setBugReports(data.bug_reports || []);
      setRegressionTests(data.regression_tests || []);
      setRegressionExecutionResult(data.regression_execution_result || null);
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
    if (status === 'waiting') return '⟳';
    if (status === 'skipped') return '⏭';
    if (status === 'not-required') return '-';
    if (status === 'not-available') return '?';
    return '○';
  };

  // Helper to format duration
  const formatDuration = (duration) => {
    if (duration === null || duration === undefined) {
      return 'N/A';
    }
    return `${duration.toFixed(3)}s`;
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
          <div className="input-row">
            <div>
              <label>Base URL:</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://127.0.0.1:8001"
              />
            </div>
            <div>
              <label>SUT ID (optional):</label>
              <input
                type="text"
                value={sutId}
                onChange={(e) => setSutId(e.target.value)}
                placeholder="e.g., demo_app"
              />
            </div>
          </div>
          <div className="input-row">
            <div>
              <label>SUT Context (JSON):</label>
              <textarea
                value={sutContext}
                onChange={(e) => setSutContext(e.target.value)}
                placeholder='e.g., {"page": "login"}'
                rows={2}
              />
            </div>
            <div>
              <label>Test Data (JSON):</label>
              <textarea
                value={testData}
                onChange={(e) => setTestData(e.target.value)}
                placeholder='e.g., {"username": "testuser", "password": "securepass"}'
                rows={2}
              />
            </div>
          </div>
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
            {/* Requirement Display */}
            <section className="requirement-section">
              <h2>Requirement</h2>
              <p>{requirement}</p>
            </section>

            {/* Test Scenarios */}
            <section className="result-section">
              <h2>Test Scenarios</h2>
              {testScenarios.length > 0 ? (
                <div>
                  {testScenarios.map((scenario, index) => (
                    <div key={index} className="scenario-card">
                      <h3>Scenario {index + 1}</h3>
                      <p><strong>Title:</strong> {scenario.title || 'N/A'}</p>
                      <p><strong>Description:</strong> {scenario.description || 'N/A'}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="null-text">No test scenarios available.</p>
              )}
            </section>

            {/* Structured Test Cases */}
            <section className="result-section">
              <h2>Structured Test Cases</h2>
              {testCases.length > 0 ? (
                <div>
                  {testCases.map((testCase, index) => (
                    <div key={index} className="test-case-card">
                      <h3>Test Case {index + 1}</h3>
                      <p><strong>Test ID:</strong> {testCase.test_id || 'N/A'}</p>
                      <p><strong>Title:</strong> {testCase.title || 'N/A'}</p>
                      <p><strong>Test Type:</strong> {testCase.test_type || 'N/A'}</p>
                      <p><strong>Expected Result:</strong> {testCase.expected_result || 'N/A'}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="null-text">No structured test cases available.</p>
              )}
            </section>

            {/* Execution Summary */}
            <section className="result-section">
              <h2>Execution Summary</h2>
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
              {executionSummary ? (
                <div className="summary-details">
                  <h3>Execution Details</h3>
                  <div>
                    <strong>Total Tests:</strong> {executionSummary.total}
                  </div>
                  <div>
                    <strong>Passed:</strong> {executionSummary.passed}
                  </div>
                  <div>
                    <strong>Failed:</strong> {executionSummary.failed}
                  </div>
                  <div>
                    <strong>Errors:</strong> {executionSummary.errors}
                  </div>
                  <div>
                    <strong>Skipped:</strong> {executionSummary.skipped}
                  </div>
                </div>
              ) : (
                <p className="null-text">No execution summary available.</p>
              )}
            </section>

            {/* Individual Test Results */}
            <section className="result-section">
              <h2>Individual Test Results</h2>
              {executionResults.length > 0 ? (
                <div>
                  {executionResults.map((result, index) => (
                    <div key={index} className="individual-result-card">
                      <h3>Test Result {index + 1}</h3>
                      <div>
                        <strong>Test ID:</strong> {result.test_id || 'N/A'}
                      </div>
                      <div>
                        <strong>Title:</strong> {result.title || 'N/A'}
                      </div>
                      <div>
                        <strong>Test Type:</strong> {result.test_type || 'N/A'}
                      </div>
                      <div>
                        <strong>Status:</strong> {getStatusIcon(result.status)} {result.status || 'N/A'}
                      </div>
                      <div>
                        <strong>Duration:</strong> {formatDuration(result.duration)}
                      </div>
                      {result.exception && (
                        <div>
                          <strong>Exception:</strong> {result.exception.type}: {result.exception.message}
                        </div>
                      )}
                      {result.stdout && (
                        <div>
                          <strong>Standard Output:</strong> {result.stdout}
                        </div>
                      )}
                      {result.stderr && (
                        <div>
                          <strong>Standard Error:</strong> {result.stderr}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="null-text">No individual test results available.</p>
              )}
            </section>

            {/* Workflow Stages Visualization */}
            <section className="workflow-stages">
              <h2>Workflow Stages</h2>
              <div className="stages-flow">
                <div className="stage">
                  <div className="stage-icon">{getStatusIcon(workflowStatus === 'pass' || workflowStatus === 'completed' ? 'completed' : workflowStatus === 'fail' ? 'failed' : 'pending')}</div>
                  <div className="stage-label">Requirement</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{testCases.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                  <div className="stage-label">Test Case Generation</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{generatedTestCode ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                  <div className="stage-label">Selenium Test Generation</div>
                </div>
                <div className="arrow">→</div>
                <div className="stage">
                  <div className="stage-icon">{executionResults.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
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
                      <div className="stage-icon">{failureAnalyses.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Failure Investigation</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{verificationResults.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Verification</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{bugReports.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
                      <div className="stage-label">Bug Report</div>
                    </div>
                    <div className="arrow">→</div>
                    <div className="stage">
                      <div className="stage-icon">{regressionTests.length > 0 ? getStatusIcon('completed') : getStatusIcon('pending')}</div>
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

            {/* Generated Test Case (backward compatibility) */}
            {testCase && (
              <section className="result-section">
                <h2>Generated Test Case</h2>
                {renderContent(testCase)}
              </section>
            )}

            {/* Generated Selenium Code */}
            {generatedTestCode && (
              <section className="result-section">
                <h2>Generated Selenium Code</h2>
                <pre className="code-block">{generatedTestCode}</pre>
              </section>
            )}

            {/* Execution Result (detailed, backward compatibility) */}
            {executionResult && (
              <section className="result-section">
                <h2>Execution Result</h2>
                {renderContent(executionResult)}
              </section>
            )}

            {/* Retrieved Knowledge */}
            {failureDetected && retrievedKnowledge && (
              <section className="result-section">
                <h2>Retrieved Knowledge</h2>
                {renderContent(retrievedKnowledge)}
              </section>
            )}

            {/* Failure Investigation - with specific fields */}
            {failureDetected && failureAnalyses.length > 0 && (
              <section className="result-section">
                <h2>Failure Investigation</h2>
                {failureAnalyses.map((fa, index) => (
                  <div key={index} className="failure-card">
                    <div>
                      <strong>Failed Test:</strong> {fa.test_case?.test_id || fa.test_case?.title || 'N/A'}
                    </div>
                    <div>
                      <strong>Execution Status:</strong> {fa.execution_status || 'N/A'}
                    </div>
                    <div>
                      <strong>Failure Summary:</strong> {fa.failure_summary || 'N/A'}
                    </div>
                    <div>
                      <strong>Probable Root Cause:</strong> {fa.probable_root_cause || 'N/A'}
                    </div>
                    <div>
                      <strong>Evidence:</strong> {Array.isArray(fa.evidence) ? fa.evidence.join(', ') : fa.evidence || 'N/A'}
                    </div>
                    <div>
                      <strong>Confidence:</strong> {(fa.confidence * 100).toFixed(1)}%
                    </div>
                    {fa.severity && (
                      <div>
                        <strong>Severity:</strong> {fa.severity}
                      </div>
                    )}
                    {fa.suggested_owner && (
                      <div>
                        <strong>Suggested Owner:</strong> {fa.suggested_owner}
                      </div>
                    )}
                  </div>
                ))}
              </section>
            )}

            {/* Verification Result */}
            {failureDetected && verificationResults.length > 0 && (
              <section className="result-section">
                <h2>Verification Result</h2>
                {verificationResults.map((vr, index) => (
                  <div key={index} className="verification-card">
                    <div>
                      <strong>Test ID:</strong> {vr.test_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Scenario ID:</strong> {vr.scenario_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Verdict:</strong> {vr.verdict || 'N/A'}
                    </div>
                    <div>
                      <strong>Reasoning:</strong> {vr.reasoning || 'N/A'}
                    </div>
                    {vr.evidence_gaps && (
                      <div>
                        <strong>Evidence Gaps:</strong> {Array.isArray(vr.evidence_gaps) ? vr.evidence_gaps.join(', ') : vr.evidence_gaps || 'N/A'}
                      </div>
                    )}
                    {vr.recommended_action && (
                      <div>
                        <strong>Recommended Action:</strong> {vr.recommended_action}
                      </div>
                    )}
                  </div>
                ))}
              </section>
            )}

            {/* Bug Report */}
            {failureDetected && bugReports.length > 0 && (
              <section className="result-section">
                <h2>Bug Report</h2>
                {bugReports.map((br, index) => (
                  <div key={index} className="bug-report-card">
                    <div>
                      <strong>Test ID:</strong> {br.test_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Scenario ID:</strong> {br.scenario_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Verification Verdict:</strong> {br.verification_verdict || 'N/A'}
                    </div>
                    {renderContent(br.bug_report || {})}
                  </div>
                ))}
              </section>
            )}

            {/* Regression Test */}
            {failureDetected && regressionTests.length > 0 && (
              <section className="result-section">
                <h2>Regression Test</h2>
                {regressionTests.map((rt, index) => (
                  <div key={index} className="regression-test-card">
                    <div>
                      <strong>Original Test ID:</strong> {rt.original_test_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Scenario ID:</strong> {rt.scenario_id || 'N/A'}
                    </div>
                    <div>
                      <strong>Verification Verdict:</strong> {rt.verification_verdict || 'N/A'}
                    </div>
                    {renderContent(rt.regression_test || {})}
                  </div>
                ))}
              </section>
            )}

            {/* Regression Execution Result */}
            {failureDetected && regressionExecutionResult && (
              <section className="result-section">
                <h2>Regression Execution Result</h2>
                {renderContent(regressionExecutionResult)}
              </section>
            )}

            {/* Human Approval */}
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