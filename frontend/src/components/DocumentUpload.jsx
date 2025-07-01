import React, { useState, useEffect } from 'react';
import { Upload, FileText, Brain, Mail, Save, Eye, Download, AlertCircle, CheckCircle, Clock, TrendingUp, BarChart3, FileCheck } from 'lucide-react';
const API_BASE = 'http://localhost:5000';
const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('upload');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [generatedLetter, setGeneratedLetter] = useState('');
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [serverStatus, setServerStatus] = useState('checking');

  useEffect(() => {
    loadCases();
    checkServerStatus();
  }, []);

  const checkServerStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/cases`);
      setServerStatus(response.ok ? 'connected' : 'disconnected');
    } catch (error) {
      setServerStatus('disconnected');
    }
  };

  const loadCases = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/cases`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      if (data.success) {
        setCases(data.cases);
      }
    } catch (error) {
      console.error('Error loading cases:', error);
      // Don't show alert for initial load failure
    }
  };

  const handleFileUpload = async (files) => {
    setLoading(true);
    const formData = new FormData();
    Array.from(files).forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        setUploadedFiles(data.files);
        setActiveTab('analyze');
      } else {
        alert('Error uploading files: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error uploading files:', error);
      alert('Error uploading files. Please make sure the Flask server is running on port 5000.');
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const analyzeCase = async () => {
    if (uploadedFiles.length === 0) {
      alert('Please upload files first');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          filenames: uploadedFiles.map(f => f.filename)
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        setAnalysis(data.analysis);
        setActiveTab('results');
      } else {
        alert('Error analyzing case: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error analyzing case:', error);
      alert('Error analyzing case. Please make sure the Flask server is running.');
    } finally {
      setLoading(false);
    }
  };

  const generateLetter = async () => {
    if (!analysis) {
      alert('Please analyze case first');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/generate-letter`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ analysis })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        setGeneratedLetter(data.letter);
        setActiveTab('letter');
      } else {
        alert('Error generating letter: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error generating letter:', error);
      alert('Error generating letter. Please make sure the Flask server is running.');
    } finally {
      setLoading(false);
    }
  };

  const saveCase = async () => {
    if (!analysis) return;

    try {
      const response = await fetch(`${API_BASE}/api/save-case`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          policy_analysis: analysis.policy_analysis,
          claim_analysis: analysis.claim_analysis,
          strategy: analysis.recommended_strategy,
          case_type: analysis.claim_analysis.claim_type || 'general'
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        alert('Case saved successfully!');
        loadCases();
      } else {
        alert('Error saving case: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error saving case:', error);
      alert('Error saving case. Please make sure the Flask server is running.');
    }
  };

  const downloadLetter = () => {
    const element = document.createElement('a');
    const file = new Blob([generatedLetter], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = 'negotiation_letter.txt';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const getSuccessColor = (probability) => {
    if (probability >= 0.8) return 'text-green-600';
    if (probability >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const tabs = [
    { id: 'upload', label: 'Upload Documents', icon: Upload },
    { id: 'analyze', label: 'Analyze Case', icon: Brain },
    { id: 'results', label: 'Analysis Results', icon: BarChart3 },
    { id: 'letter', label: 'Generate Letter', icon: Mail },
    { id: 'cases', label: 'Case History', icon: FileCheck }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Insurance Negotiation Agent</h1>
          <p className="text-gray-600">AI-powered insurance claim negotiation assistance</p>
          
          {/* Server Status Indicator */}
          <div className="mt-4 flex justify-center">
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
              serverStatus === 'connected' ? 'bg-green-100 text-green-800' :
              serverStatus === 'disconnected' ? 'bg-red-100 text-red-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                serverStatus === 'connected' ? 'bg-green-500' :
                serverStatus === 'disconnected' ? 'bg-red-500' :
                'bg-yellow-500'
              }`}></div>
              <span>
                {serverStatus === 'connected' ? 'Server Connected' :
                 serverStatus === 'disconnected' ? 'Server Disconnected - Start Flask app on port 5000' :
                 'Checking Connection...'}
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mb-8">
          <div className="flex flex-wrap justify-center space-x-1 bg-white rounded-lg p-1 shadow-lg">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-md transition-all duration-200 ${
                    activeTab === tab.id
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon size={18} />
                  <span className="font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-xl shadow-xl p-6">
          {/* Upload Tab */}
          {activeTab === 'upload' && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-2xl font-bold mb-4">Upload Your Documents</h2>
                <p className="text-gray-600 mb-6">Upload your insurance policy, claim documents, and correspondence</p>
              </div>
              
              <div
                className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                  dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <Upload className="mx-auto mb-4 text-gray-400" size={48} />
                <p className="text-xl mb-2">Drag and drop files here</p>
                <p className="text-gray-500 mb-4">or click to select files</p>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
                  onChange={(e) => handleFileUpload(e.target.files)}
                  className="hidden"
                  id="file-input"
                />
                <label
                  htmlFor="file-input"
                  className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg cursor-pointer hover:bg-blue-700 transition-colors"
                >
                  Select Files
                </label>
                <p className="text-sm text-gray-500 mt-2">Supported: PDF, DOCX, TXT, PNG, JPG (Max 16MB)</p>
              </div>

              {uploadedFiles.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Uploaded Files:</h3>
                  {uploadedFiles.map((file, index) => (
                    <div key={index} className="bg-gray-50 p-4 rounded-lg border">
                      <div className="flex items-center space-x-3">
                        <FileText className="text-blue-600" size={20} />
                        <div className="flex-1">
                          <p className="font-medium">{file.filename}</p>
                          <p className="text-sm text-gray-600 mt-1">{file.content}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Analyze Tab */}
          {activeTab === 'analyze' && (
            <div className="space-y-6 text-center">
              <div>
                <h2 className="text-2xl font-bold mb-4">Analyze Your Case</h2>
                <p className="text-gray-600 mb-6">
                  Our AI will analyze your documents to identify leverage points and recommend negotiation strategies
                </p>
              </div>

              {uploadedFiles.length > 0 ? (
                <div className="space-y-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <p className="text-blue-800">
                      Ready to analyze {uploadedFiles.length} document{uploadedFiles.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  
                  <button
                    onClick={analyzeCase}
                    disabled={loading || serverStatus !== 'connected'}
                    className="bg-blue-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center space-x-2 mx-auto"
                  >
                    {loading ? (
                      <>
                        <Clock className="animate-spin" size={20} />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <Brain size={20} />
                        <span>Analyze Case</span>
                      </>
                    )}
                  </button>
                  
                  {serverStatus !== 'connected' && (
                    <p className="text-red-600 text-sm text-center">
                      Please start the Flask server to analyze cases
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-yellow-50 p-4 rounded-lg">
                    <AlertCircle className="mx-auto mb-2 text-yellow-600" size={24} />
                    <p className="text-yellow-800">Please upload documents first</p>
                  </div>
                  
                  {/* Demo Button for Development */}
                  <button
                    onClick={() => {
                      // Add some demo files for testing
                      setUploadedFiles([
                        {
                          filename: 'demo_policy.pdf',
                          content: 'Demo policy document with liability coverage, collision coverage, and comprehensive coverage. Policy limits: $100,000 per occurrence...'
                        },
                        {
                          filename: 'demo_claim.pdf', 
                          content: 'Claim denied because of policy exclusion. Incident date: 03/15/2024. Damages claimed: $25,000...'
                        }
                      ]);
                      setActiveTab('analyze');
                    }}
                    className="bg-gray-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-gray-700 transition-colors mx-auto block"
                  >
                    Use Demo Files (for testing)
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Results Tab */}
          {activeTab === 'results' && (
            <div className="space-y-6">
              {analysis ? (
                <>
                  <div className="text-center mb-6">
                    <h2 className="text-2xl font-bold mb-2">Analysis Results</h2>
                    <div className={`text-3xl font-bold ${getSuccessColor(analysis.success_probability)}`}>
                      {Math.round(analysis.success_probability * 100)}% Success Probability
                    </div>
                  </div>

                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Strategy Card */}
                    <div className="bg-blue-50 p-6 rounded-lg">
                      <h3 className="text-lg font-semibold mb-3 text-blue-800">Recommended Strategy</h3>
                      <div className="space-y-2">
                        <p className="font-medium capitalize">{analysis.recommended_strategy.replace(/_/g, ' ')}</p>
                        <div className="flex items-center space-x-2">
                          <TrendingUp size={16} className="text-green-600" />
                          <span className="text-sm">Strategy Score: {Math.round(analysis.strategy_score * 100)}%</span>
                        </div>
                      </div>
                    </div>

                    {/* Leverage Points */}
                    <div className="bg-green-50 p-6 rounded-lg">
                      <h3 className="text-lg font-semibold mb-3 text-green-800">Leverage Points</h3>
                      <div className="space-y-2">
                        {analysis.leverage_points.map((point, index) => (
                          <div key={index} className="flex items-start space-x-2">
                            <CheckCircle size={16} className="text-green-600 mt-0.5" />
                            <div>
                              <p className="text-sm font-medium">{point.type.replace(/_/g, ' ')}</p>
                              <p className="text-xs text-gray-600">{point.description}</p>
                              <span className="text-xs bg-green-200 text-green-800 px-2 py-1 rounded">
                                Strength: {Math.round(point.strength * 100)}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Policy Analysis */}
                  <div className="bg-gray-50 p-6 rounded-lg">
                    <h3 className="text-lg font-semibold mb-3">Policy Analysis</h3>
                    <div className="grid md:grid-cols-3 gap-4">
                      <div>
                        <h4 className="font-medium text-blue-800 mb-2">Coverage Types</h4>
                        <ul className="text-sm space-y-1">
                          {analysis.policy_analysis.coverage_types.map((type, index) => (
                            <li key={index} className="bg-blue-100 px-2 py-1 rounded">{type}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-medium text-red-800 mb-2">Exclusions</h4>
                        <ul className="text-sm space-y-1">
                          {analysis.policy_analysis.exclusions.map((exclusion, index) => (
                            <li key={index} className="bg-red-100 px-2 py-1 rounded">{exclusion}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-medium text-yellow-800 mb-2">Key Clauses</h4>
                        <ul className="text-sm space-y-1">
                          {analysis.policy_analysis.key_clauses.map((clause, index) => (
                            <li key={index} className="bg-yellow-100 px-2 py-1 rounded">{clause}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Claim Analysis */}
                  <div className="bg-gray-50 p-6 rounded-lg">
                    <h3 className="text-lg font-semibold mb-3">Claim Analysis</h3>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div>
                        <p><strong>Claim Amount:</strong> {analysis.claim_analysis.damages_claimed || 'Not specified'}</p>
                        <p><strong>Incident Date:</strong> {analysis.claim_analysis.incident_date || 'Not found'}</p>
                        <p><strong>Claim Type:</strong> {analysis.claim_analysis.claim_type || 'General'}</p>
                      </div>
                      <div>
                        <h4 className="font-medium mb-2">Denial Reasons</h4>
                        <ul className="text-sm space-y-1">
                          {analysis.claim_analysis.denial_reasons.map((reason, index) => (
                            <li key={index} className="bg-orange-100 px-2 py-1 rounded">{reason}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  <div className="flex space-x-4 justify-center">
                    <button
                      onClick={generateLetter}
                      className="bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center space-x-2"
                    >
                      <Mail size={20} />
                      <span>Generate Letter</span>
                    </button>
                    <button
                      onClick={saveCase}
                      className="bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors flex items-center space-x-2"
                    >
                      <Save size={20} />
                      <span>Save Case</span>
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-center">
                  <AlertCircle className="mx-auto mb-4 text-gray-400" size={48} />
                  <p className="text-gray-600">No analysis results yet. Please analyze your case first.</p>
                </div>
              )}
            </div>
          )}

          {/* Letter Tab */}
          {activeTab === 'letter' && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-2xl font-bold mb-4">Generated Negotiation Letter</h2>
                {analysis && (
                  <p className="text-gray-600">
                    Using strategy: <span className="font-semibold capitalize">{analysis.recommended_strategy.replace(/_/g, ' ')}</span>
                  </p>
                )}
              </div>

              {generatedLetter ? (
                <div className="space-y-4">
                  <div className="bg-gray-50 p-6 rounded-lg border">
                    <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed">
                      {generatedLetter}
                    </pre>
                  </div>
                  
                  <div className="flex space-x-4 justify-center">
                    <button
                      onClick={downloadLetter}
                      className="bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors flex items-center space-x-2"
                    >
                      <Download size={20} />
                      <span>Download Letter</span>
                    </button>
                    <button
                      onClick={() => navigator.clipboard.writeText(generatedLetter)}
                      className="bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                    >
                      Copy to Clipboard
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <Mail className="mx-auto mb-4 text-gray-400" size={48} />
                  <p className="text-gray-600 mb-4">No letter generated yet.</p>
                  {analysis && (
                    <button
                      onClick={generateLetter}
                      disabled={loading}
                      className="bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors disabled:opacity-50"
                    >
                      {loading ? 'Generating...' : 'Generate Letter'}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Cases Tab */}
          {activeTab === 'cases' && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-2xl font-bold mb-4">Case History</h2>
                <p className="text-gray-600">Track your insurance negotiation cases</p>
              </div>

              {cases.length > 0 ? (
                <div className="space-y-4">
                  {cases.map((caseItem) => (
                    <div key={caseItem.id} className="bg-gray-50 p-4 rounded-lg border">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-semibold capitalize">{caseItem.case_type}</h3>
                          <p className="text-sm text-gray-600">Created: {new Date(caseItem.created_at).toLocaleDateString()}</p>
                          <p className="text-sm">Strategy: <span className="capitalize">{caseItem.strategy_used.replace(/_/g, ' ')}</span></p>
                        </div>
                        <div className="text-right">
                          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                            caseItem.status === 'active' ? 'bg-green-100 text-green-800' :
                            caseItem.status === 'completed' ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {caseItem.status}
                          </span>
                          {caseItem.success_score && (
                            <p className="text-sm mt-1">Success: {Math.round(caseItem.success_score * 100)}%</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center">
                  <FileCheck className="mx-auto mb-4 text-gray-400" size={48} />
                  <p className="text-gray-600">No cases saved yet.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {loading && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white p-6 rounded-lg flex items-center space-x-3">
              <Clock className="animate-spin text-blue-600" size={24} />
              <span className="text-lg">Processing...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;