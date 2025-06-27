import React, { useState, useEffect } from 'react';
import { 
  Upload, 
  FileText, 
  DollarSign, 
  TrendingUp, 
  Clock, 
  CheckCircle, 
  AlertCircle, 
  Eye, 
  Download,
  BarChart3,
  PieChart,
  Target,
  Users,
  Calendar,
  Mail,
  RefreshCw,
  Search,
  Filter,
  Plus
} from 'lucide-react';

const Dashboard = () => {
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  // Mock data for demonstration - replace with actual API calls
  const mockCases = [
    {
      case_id: "CASE_20241215_143022",
      claim_type: "denial_letter",
      policy_number: "AUTO-2024-567890",
      success_probability: 0.78,
      estimated_payout: 4200,
      created_at: "2024-12-15T14:30:22",
      status: "active",
      strategy: {
        name: "Policy Interpretation Challenge",
        approach: "assertive",
        confidence: 0.82
      },
      extracted_info: {
        extraction_confidence: 0.85,
        monetary_amounts: ["$1,500", "$2,800"],
        document_type: "denial_letter"
      }
    },
    {
      case_id: "CASE_20241214_091534",
      claim_type: "settlement_offer",
      policy_number: "HOME-2024-123456",
      success_probability: 0.65,
      estimated_payout: 6800,
      created_at: "2024-12-14T09:15:34",
      status: "completed",
      strategy: {
        name: "Market Value Documentation",
        approach: "data_driven",
        confidence: 0.71
      },
      extracted_info: {
        extraction_confidence: 0.92,
        monetary_amounts: ["$3,200", "$5,800"],
        document_type: "settlement_offer"
      }
    },
    {
      case_id: "CASE_20241213_165411",
      claim_type: "policy_document",
      policy_number: "AUTO-2024-789012",
      success_probability: 0.55,
      estimated_payout: 2100,
      created_at: "2024-12-13T16:54:11",
      status: "pending",
      strategy: {
        name: "Coverage Scope Expansion",
        approach: "collaborative",
        confidence: 0.58
      },
      extracted_info: {
        extraction_confidence: 0.73,
        monetary_amounts: ["$1,200"],
        document_type: "policy_document"
      }
    }
  ];

  useEffect(() => {
  fetch("http://localhost:8000/api/cases")
    .then(res => res.json())
    .then(data => setCases(data.cases))
    .catch(err => console.error("Failed to load cases", err));
}, []);

const downloadPdfLetter = async () => {
  try {
    const response = await fetch(`http://localhost:8000/api/cases/${selectedCase.case_id}/letter-pdf`);
    if (!response.ok) throw new Error("Failed to download letter");
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `negotiation_letter_${selectedCase.case_id}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    console.error('Download failed:', error);
  }
};

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadedFile(file);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Simulate API call
      const response = await fetch("http://localhost:8000/api/upload", {
  method: "POST",
  body: formData,
});

if (!response.ok) throw new Error("Upload failed");

const data = await response.json();
const newCase = {
  case_id: data.case_id,
  claim_type: data.extracted_info?.document_type || "unknown",
  policy_number: data.extracted_info?.policy_details?.policy_number || "unknown",
  success_probability: data.analysis?.success_probability || 0,
  estimated_payout: data.analysis?.estimated_payout_range?.expected || 0,
  created_at: new Date().toISOString(),
  status: "active",
  strategy: data.strategy || {},

  extracted_info: data.extracted_info || {},
};

setCases(prev => [newCase, ...prev]);
setSelectedCase(newCase);
setIsUploading(false);
setActiveTab('analysis');


    } catch (error) {
      console.error('Upload failed:', error);
      setIsUploading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'text-blue-600 bg-blue-100';
      case 'completed': return 'text-green-600 bg-green-100';
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const filteredCases = cases.filter(case_ => {
    const matchesSearch = case_.policy_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         case_.case_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || case_.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const totalPayout = cases.reduce((sum, case_) => sum + case_.estimated_payout, 0);
  const avgSuccessRate = cases.reduce((sum, case_) => sum + case_.success_probability, 0) / cases.length || 0;
  const activeCases = cases.filter(case_ => case_.status === 'active').length;

  const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-white rounded-xl shadow-lg p-6 border-l-4" style={{ borderLeftColor: color }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <Icon className="h-8 w-8" style={{ color }} />
      </div>
    </div>
  );

  const CaseCard = ({ case_ }) => (
    <div 
      className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-blue-500"
      onClick={() => {
        setSelectedCase(case_);
        setActiveTab('analysis');
      }}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">{case_.case_id}</h3>
          <p className="text-sm text-gray-600">{case_.policy_number}</p>
        </div>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(case_.status)}`}>
          {case_.status.charAt(0).toUpperCase() + case_.status.slice(1)}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-500">Success Probability</p>
          <p className={`font-semibold ${getConfidenceColor(case_.success_probability)}`}>
            {(case_.success_probability * 100).toFixed(0)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Est. Payout</p>
          <p className="font-semibold text-green-600">${case_.estimated_payout.toLocaleString()}</p>
        </div>
      </div>
      
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">
          {new Date(case_.created_at).toLocaleDateString()}
        </span>
        <span className="text-xs font-medium text-blue-600">
          {case_.strategy.name}
        </span>
      </div>
    </div>
  );

  const NegotiationLetter = ({ case_ }) => (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center">
        <Mail className="h-5 w-5 mr-2 text-blue-600" />
        Generated Negotiation Letter
      </h3>
      
      <div className="bg-gray-50 rounded-lg p-4 mb-4">
        <p className="font-medium text-gray-900 mb-2">
          Subject: Re: Claim Review - {case_.policy_number}
        </p>
        <div className="text-sm text-gray-700 space-y-2">
          <p>Dear Claims Adjuster,</p>
          <p>I am writing regarding my insurance claim for Policy #{case_.policy_number}.</p>
          <p>After careful review of the policy terms and claim details, I believe there are several important factors that warrant reconsideration:</p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>Policy coverage clearly applies to this type of incident</li>
            <li>All documentation has been provided in accordance with policy requirements</li>
            <li>The settlement amount does not reflect the actual damages incurred</li>
          </ul>
          <p>Based on similar cases and industry standards, I believe a fair settlement would be in the range of ${case_.estimated_payout.toLocaleString()}.</p>
          <p>I have attached supporting documentation and would welcome the opportunity to discuss this matter further.</p>
          <p>Sincerely,<br/>[Your Name]</p>
        </div>
      </div>
      
      <div className="flex space-x-3">
        <button 
          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          onClick={downloadPdfLetter}
        >
          <Download className="h-4 w-4 mr-2" />
          Download Letter
        </button>
        <button className="flex items-center px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
          <Mail className="h-4 w-4 mr-2" />
          Email Letter
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">AI Insurance Negotiation Agent</h1>
              <p className="text-gray-600">Maximize your insurance claims with AI-powered negotiation</p>
            </div>
            <div className="flex items-center space-x-4">
              <label className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors cursor-pointer">
                <Upload className="h-4 w-4 mr-2" />
                Upload Document
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={isUploading}
                />
              </label>
              {isUploading && (
                <div className="flex items-center text-blue-600">
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Analyzing...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation Tabs */}
        <div className="mb-8">
          <nav className="flex space-x-8">
            {[
              { id: 'overview', label: 'Overview', icon: BarChart3 },
              { id: 'cases', label: 'Cases', icon: FileText },
              { id: 'analysis', label: 'Analysis', icon: Target },
              { id: 'letters', label: 'Letters', icon: Mail }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center px-3 py-2 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Icon className="h-4 w-4 mr-2" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatCard
                title="Total Cases"
                value={cases.length}
                icon={FileText}
                color="#3B82F6"
                subtitle="All time"
              />
              <StatCard
                title="Active Cases"
                value={activeCases}
                icon={Clock}
                color="#F59E0B"
                subtitle="In progress"
              />
              <StatCard
                title="Avg Success Rate"
                value={`${(avgSuccessRate * 100).toFixed(0)}%`}
                icon={TrendingUp}
                color="#10B981"
                subtitle="Probability"
              />
              <StatCard
                title="Total Est. Payout"
                value={`$${totalPayout.toLocaleString()}`}
                icon={DollarSign}
                color="#8B5CF6"
                subtitle="Potential recovery"
              />
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
              <div className="space-y-4">
                {cases.slice(0, 3).map((case_) => (
                  <div key={case_.case_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <FileText className="h-5 w-5 text-blue-600 mr-3" />
                      <div>
                        <p className="font-medium text-gray-900">{case_.case_id}</p>
                        <p className="text-sm text-gray-600">{case_.policy_number}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-green-600">${case_.estimated_payout.toLocaleString()}</p>
                      <p className="text-sm text-gray-500">{new Date(case_.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Cases Tab */}
        {activeTab === 'cases' && (
          <div className="space-y-6">
            {/* Search and Filter */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="relative">
                <Search className="h-4 w-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search cases..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div className="flex items-center space-x-2">
                <Filter className="h-4 w-4 text-gray-400" />
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="all">All Status</option>
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                  <option value="pending">Pending</option>
                </select>
              </div>
            </div>

            {/* Cases Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCases.map((case_) => (
                <CaseCard key={case_.case_id} case_={case_} />
              ))}
            </div>
          </div>
        )}

        {/* Analysis Tab */}
        {activeTab === 'analysis' && selectedCase && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold mb-4">Case Analysis: {selectedCase.case_id}</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-medium text-gray-900 mb-3">Case Details</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Policy Number:</span>
                      <span className="font-medium">{selectedCase.policy_number}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Document Type:</span>
                      <span className="font-medium">{selectedCase.extracted_info.document_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Created:</span>
                      <span className="font-medium">{new Date(selectedCase.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(selectedCase.status)}`}>
                        {selectedCase.status}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="font-medium text-gray-900 mb-3">Strategy Analysis</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Strategy:</span>
                      <span className="font-medium">{selectedCase.strategy?.name || "N/A"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Approach:</span>
                      <span className="font-medium">{selectedCase.strategy.approach}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Success Probability:</span>
                      <span className={`font-bold ${getConfidenceColor(selectedCase.success_probability)}`}>
                        {(selectedCase.success_probability * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Est. Payout:</span>
                      <span className="font-bold text-green-600">
  ${typeof selectedCase.estimated_payout === 'object'
    ? selectedCase.estimated_payout?.expected?.toLocaleString?.() || "0"
    : selectedCase.estimated_payout?.toLocaleString?.()}
</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommended Actions */}
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Recommended Actions</h4>
                {selectedCase.strategy?.recommended_actions?.length > 0 ? (
                  <ul className="text-sm text-blue-700 space-y-1">
                    {selectedCase.strategy.recommended_actions.map((action, index) => (
                      <li key={index}>• {action}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-blue-500 italic">No recommendations available for this case.</p>
                )}
              </div>

{/* Negotiation Plan Timeline */}
              {selectedCase.strategy?.negotiation_plan?.rounds?.length > 0 && (
                <div className="mt-6 p-4 bg-white rounded-lg shadow">
                  <h4 className="font-semibold text-gray-900 mb-4">Negotiation Plan Timeline</h4>
                  <div className="space-y-4">
                    {selectedCase.strategy.negotiation_plan.rounds.map((round) => (
                      <div key={round.round} className="border-l-4 border-blue-500 pl-4">
                        <p className="text-sm text-blue-600 font-semibold">Round {round.round}: {round.objective}</p>
                        <ul className="list-disc list-inside text-sm text-gray-700 pl-2 mt-1">
                          {round.key_actions?.map((action, idx) => (
                            <li key={idx}>{action}</li>
                          ))}
                        </ul>
                        <p className="text-xs text-gray-500 mt-1">Expected Outcome: {round.expected_outcome}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          </div>
        )}

        {/* Letters Tab */}
        {activeTab === 'letters' && (
          <div className="space-y-6">
            {selectedCase ? (
              <NegotiationLetter case_={selectedCase} />
            ) : (
              <div className="bg-white rounded-lg shadow-md p-8 text-center">
                <Mail className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Case Selected</h3>
                <p className="text-gray-600">Select a case from the Cases tab to view or generate negotiation letters.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;