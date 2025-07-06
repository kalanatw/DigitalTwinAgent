// Email Management JavaScript - Event-Driven Architecture

function emailManagementApp() {
    return {
        // State
        isLoading: false,
        errorMessage: '',
        searchQuery: '',
        emails: [],
        nextPageToken: null,
        viewMode: 'detailed', // 'compact' or 'detailed'
        connectionStatus: {
            connected: {{ has_gmail_connection|yesno:"true,false" }},
            email: '{{ connected_email|default:"" }}'
        },

        // Agent and Twin data
        activeAgent: {
            id: '{{ agent_id|default:"" }}',
            name: '{{ agent_name|default:"No Agent Selected" }}',
            twin_version: '{{ twin_version_name|default:"Default" }}'
        },
        availableAgents: [],
        availableTwinVersions: [],
        selectedAgent: '',
        selectedTwinVersion: '',
        selectedTone: 'professional',
        additionalContext: '',

        // Modal states - Clean separation
        selectedEmail: null,
        selectedEmailId: null,
        showEmailModal: false,
        showAgentSelector: false,
        showComposeModal: false,
        
        // Agent selection state
        selectedAgentId: null,
        selectedTwinVersionId: null,
        
        // UI state
        isTransitioning: false,
        lastScrollPosition: 0,
        isGenerating: false,
        
        // Reply tones with icons
        replyTones: [
            { value: 'professional', label: 'Professional', icon: 'fas fa-briefcase' },
            { value: 'friendly', label: 'Friendly', icon: 'fas fa-smile' },
            { value: 'formal', label: 'Formal', icon: 'fas fa-user-tie' },
            { value: 'casual', label: 'Casual', icon: 'fas fa-coffee' }
        ],

        // Loading states
        isSendingEmail: false,
        isSending: false,

        // Initialize
        init() {
            console.log('Initializing clean email management app...');
            
            // Clean initial state
            this.selectedEmail = null;
            this.selectedEmailId = null;
            this.showEmailModal = false;
            
            // Event listeners for component communication
            this.setupEventListeners();
            
            // Load initial data
            this.checkConnectionStatus();
            this.loadActiveAgent();
            if (this.connectionStatus.connected) {
                this.loadEmails();
            }
            
            console.log('Clean email app initialized:', {
                selectedEmail: this.selectedEmail,
                showEmailModal: this.showEmailModal
            });
        },

        // Event-driven component communication
        setupEventListeners() {
            // Listen for email selection from list component
            this.$el.addEventListener('email-selected', (event) => {
                console.log('Main app: email selected event received', event.detail);
                this.handleEmailSelection(event.detail.email);
            });
            
            // Listen for modal close from modal component
            this.$el.addEventListener('close-email-modal', () => {
                console.log('Main app: close modal event received');
                this.closeEmailModal();
            });
            
            // Listen for load more emails
            this.$el.addEventListener('load-more-emails', () => {
                this.loadMoreEmails();
            });
        },

        // Clean email selection handler
        handleEmailSelection(email) {
            console.log('Handling email selection:', email);
            
            if (!email || !email.id) {
                console.error('Invalid email object:', email);
                return;
            }
            
            // Don't open modal if loading
            if (this.isLoading || this.isTransitioning) {
                console.log('Ignoring email selection - app is busy');
                return;
            }
            
            // Set selected email and open modal
            this.selectedEmail = email;
            this.selectedEmailId = email.id;
            this.showEmailModal = true;
            
            console.log('Email modal should open:', {
                selectedEmail: this.selectedEmail,
                showEmailModal: this.showEmailModal,
                modalCondition: !!(this.showEmailModal && this.selectedEmail && this.selectedEmail.id)
            });
            
            // Prevent background scrolling
            document.body.style.overflow = 'hidden';
            
            // Debug modal visibility
            this.$nextTick(() => {
                const modalElement = document.querySelector('[x-show*="selectedEmail"]');
                console.log('Modal visibility check:', {
                    element: modalElement,
                    computed: modalElement ? window.getComputedStyle(modalElement).display : 'no element found'
                });
            });
        },
        
        // Clean modal close
        closeEmailModal() {
            console.log('Closing email modal');
            
            if (this.isTransitioning) return;
            
            this.isTransitioning = true;
            this.showEmailModal = false;
            
            // Restore background scrolling
            document.body.style.overflow = '';
            
            setTimeout(() => {
                this.selectedEmail = null;
                this.selectedEmailId = null;
                this.isTransitioning = false;
            }, 200);
        },

        // API Methods
        async checkConnectionStatus() {
            // Implementation for checking Gmail connection
            console.log('Checking connection status');
        },

        async loadActiveAgent() {
            // Implementation for loading active agent
            console.log('Loading active agent');
        },

        async loadEmails() {
            if (this.isLoading) return;
            
            this.isLoading = true;
            this.errorMessage = '';
            
            try {
                console.log('Loading emails...');
                
                const response = await fetch('/api/gmail/emails/', {
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                
                if (!response.ok) {
                    throw new Error('Failed to load emails');
                }
                
                const data = await response.json();
                this.emails = data.emails || [];
                this.nextPageToken = data.nextPageToken;
                
                console.log(`Loaded ${this.emails.length} emails`);
                
            } catch (error) {
                console.error('Error loading emails:', error);
                this.errorMessage = 'Failed to load emails. Please try again.';
            } finally {
                this.isLoading = false;
            }
        },

        async loadMoreEmails() {
            if (!this.nextPageToken || this.isLoading) return;
            
            console.log('Loading more emails...');
            // Implementation for loading more emails
        },

        async refreshEmails() {
            console.log('Refreshing emails...');
            this.emails = [];
            this.nextPageToken = null;
            await this.loadEmails();
        },

        async searchEmails() {
            console.log('Searching emails with query:', this.searchQuery);
            // Implementation for email search
        },

        clearSearch() {
            this.searchQuery = '';
            this.refreshEmails();
        },

        async loadUnreadEmails() {
            console.log('Loading unread emails...');
            // Implementation for loading unread emails
        },

        async loadTodayEmails() {
            console.log('Loading today\'s emails...');
            // Implementation for loading today's emails
        },

        toggleViewMode() {
            this.viewMode = this.viewMode === 'compact' ? 'detailed' : 'compact';
            console.log('View mode toggled to:', this.viewMode);
        },

        // Utility methods
        formatDate(date) {
            if (!date) return '';
            const now = new Date();
            const emailDate = new Date(date);
            const diffTime = Math.abs(now - emailDate);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays === 1) {
                return 'Today';
            } else if (diffDays === 2) {
                return 'Yesterday';
            } else if (diffDays <= 7) {
                return `${diffDays - 1} days ago`;
            } else {
                return emailDate.toLocaleDateString();
            }
        },

        formatDetailedDate(date) {
            if (!date) return '';
            return new Date(date).toLocaleString();
        }
    }
}
