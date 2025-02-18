import { useState, useEffect } from 'react'
import { DatePicker } from '@mui/x-date-pickers'
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  ButtonGroup,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  LinearProgress,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import ImageIcon from '@mui/icons-material/Image'
import SaveIcon from '@mui/icons-material/Save'
import HistoryIcon from '@mui/icons-material/History'
import DatasetIcon from '@mui/icons-material/Dataset'
import dayjs, { Dayjs } from 'dayjs'
import axios from 'axios'

interface Message {
  id: string
  content: string
  timestamp: string
  author: {
    id: string
    username: string
  }
  attachments: Array<{
    url: string
    filename: string
  }>
  referenced_message?: {
    id: string
    content: string
    timestamp: string
    author: {
      id: string
      username: string
    }
    attachments: Array<{
      url: string
      filename: string
    }>
  }
}

interface ScrapeResponse {
  messages: Message[]
  message_count: number
  download_urls: {
    json: string
    attachments: string
    dataset: string
  }
}

interface SavedChannel {
  id: string
  name: string | null
}

export default function DiscordScraper() {
  const [token, setToken] = useState('')
  const [channelId, setChannelId] = useState('')
  const [startDate, setStartDate] = useState<Dayjs | null>(dayjs())
  const [messageLimit, setMessageLimit] = useState(1000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [messageCount, setMessageCount] = useState(0)
  const [downloadUrls, setDownloadUrls] = useState<{
    json: string;
    attachments: string;
    dataset: string;
  } | null>(null)
  const [downloading, setDownloading] = useState<'json' | 'attachments' | 'dataset' | null>(null)
  const [savedChannels, setSavedChannels] = useState<SavedChannel[]>([])
  const [channelMenuAnchor, setChannelMenuAnchor] = useState<null | HTMLElement>(null)
  const [downloadProgress, setDownloadProgress] = useState(0)

  useEffect(() => {
    // Load saved token and channels on component mount
    loadSavedCredentials()
    loadSavedChannels()
  }, [])

  const loadSavedCredentials = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/credentials/latest')
      setToken(response.data.token)
    } catch (err) {
      // Ignore error if no saved credentials
      console.log('No saved credentials found')
    }
  }

  const loadSavedChannels = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/channels')
      setSavedChannels(response.data.channels)
    } catch (err) {
      console.error('Error loading saved channels:', err)
    }
  }

  const handleSaveCredentials = async () => {
    if (!token) return
    try {
      await axios.post('http://localhost:8000/api/credentials/save', { token })
      // Show success message
    } catch (err) {
      setError('Failed to save credentials')
    }
  }

  const handleSaveChannel = async () => {
    if (!channelId) return
    try {
      await axios.post('http://localhost:8000/api/channels/save', { 
        channel_id: channelId,
        name: `Channel ${channelId}` // You could prompt for a name if desired
      })
      loadSavedChannels()
    } catch (err) {
      setError('Failed to save channel')
    }
  }

  const handleChannelSelect = (channel: SavedChannel) => {
    setChannelId(channel.id)
    setChannelMenuAnchor(null)
  }

  const handleSubmit = async () => {
    if (!token || !channelId || !startDate) {
      setError('Please fill in all required fields')
      return
    }

    setLoading(true)
    setError('')
    setMessages([])
    setMessageCount(0)
    setDownloadUrls(null)

    try {
      const response = await axios.post<ScrapeResponse>('http://localhost:8000/api/scrape', {
        token,
        channel_id: channelId,
        start_date: startDate.format('YYYY-MM-DD'),
        message_limit: messageLimit,
      })

      setMessages(response.data.messages)
      setMessageCount(response.data.message_count)
      setDownloadUrls(response.data.download_urls)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async (type: 'json' | 'attachments' | 'dataset') => {
    if (!downloadUrls) return

    setDownloading(type)
    setError('')
    
    try {
      const url = `http://localhost:8000${downloadUrls[type]}`
      
      // Create custom axios instance with increased timeout
      const axiosInstance = axios.create({
        timeout: 300000, // 5 minute timeout
        responseType: 'blob',
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setDownloadProgress(percentCompleted)
          }
        }
      })

      const response = await axiosInstance.get(url)
      
      // Use the native browser download API
      const blob = new Blob([response.data])
      const downloadUrl = window.URL.createObjectURL(blob)
      
      const filename = type === 'json' 
        ? `discord_messages_${channelId}.json`
        : type === 'attachments'
        ? `discord_attachments_${channelId}.zip`
        : `discord_dataset_${channelId}.zip`

      // Create an invisible anchor and click it
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      
      // Cleanup
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
      setDownloadProgress(0)
    } catch (err) {
      if (axios.isAxiosError(err) && err.code === 'ECONNABORTED') {
        setError(`Download timeout. The ${type} file is too large or the connection is slow.`)
      } else {
        setError(`Error downloading ${type} file: ${err instanceof Error ? err.message : 'Unknown error'}`)
      }
    } finally {
      setDownloading(null)
    }
  }

  return (
    <Box sx={{ width: '100%', mt: 3 }}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <TextField
              label="Discord Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              type="password"
              fullWidth
            />
            <Tooltip title="Save Token">
              <IconButton onClick={handleSaveCredentials} color="primary">
                <SaveIcon />
              </IconButton>
            </Tooltip>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <TextField
              label="Channel ID"
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              required
              fullWidth
            />
            <Tooltip title="Save Channel">
              <IconButton onClick={handleSaveChannel} color="primary">
                <SaveIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Saved Channels">
              <IconButton 
                onClick={(e) => setChannelMenuAnchor(e.currentTarget)}
                color="primary"
              >
                <HistoryIcon />
              </IconButton>
            </Tooltip>
          </Box>

          <Menu
            anchorEl={channelMenuAnchor}
            open={Boolean(channelMenuAnchor)}
            onClose={() => setChannelMenuAnchor(null)}
          >
            {savedChannels.map((channel) => (
              <MenuItem 
                key={channel.id} 
                onClick={() => handleChannelSelect(channel)}
              >
                {channel.name || channel.id}
              </MenuItem>
            ))}
          </Menu>

          <DatePicker
            label="Start Date"
            value={startDate}
            onChange={(newValue) => setStartDate(newValue)}
          />
          <TextField
            label="Message Limit"
            type="number"
            value={messageLimit}
            onChange={(e) => setMessageLimit(Number(e.target.value))}
            required
          />
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={loading}
            sx={{ mt: 2 }}
          >
            {loading ? <CircularProgress size={24} /> : 'Scrape Messages'}
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {messageCount > 0 && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Successfully scraped {messageCount} messages
        </Alert>
      )}

      {downloadUrls && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Download Options
          </Typography>
          <ButtonGroup variant="contained" sx={{ gap: 1 }}>
            <Button
              startIcon={<DownloadIcon />}
              onClick={() => handleDownload('json')}
              disabled={downloading === 'json'}
            >
              {downloading === 'json' ? (
                <CircularProgress size={24} />
              ) : (
                'Download JSON'
              )}
            </Button>
            <Button
              startIcon={<ImageIcon />}
              onClick={() => handleDownload('attachments')}
              disabled={downloading === 'attachments'}
              color="secondary"
            >
              {downloading === 'attachments' ? (
                <CircularProgress size={24} />
              ) : (
                'Download Attachments'
              )}
            </Button>
            <Button
              startIcon={<DatasetIcon />}
              onClick={() => handleDownload('dataset')}
              disabled={downloading === 'dataset'}
              color="primary"
            >
              {downloading === 'dataset' ? (
                <CircularProgress size={24} />
              ) : (
                'Download Complete Dataset'
              )}
            </Button>
          </ButtonGroup>
          {downloading && downloadProgress > 0 && (
            <Box sx={{ width: '100%', mt: 2 }}>
              <LinearProgress variant="determinate" value={downloadProgress} />
              <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                Downloading: {downloadProgress}%
              </Typography>
            </Box>
          )}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Complete dataset includes: daily JSON files, CSV summary, metadata, and all attachments
          </Typography>
        </Paper>
      )}

      {messages.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Messages
          </Typography>
          <List>
            {messages.map((message, index) => (
              <Box key={message.id}>
                <ListItem alignItems="flex-start">
                  <ListItemText
                    primary={
                      <Typography>
                        <strong>{message.author.username}</strong> -{' '}
                        {new Date(message.timestamp).toLocaleString()}
                      </Typography>
                    }
                    secondary={
                      <>
                        {message.referenced_message && (
                          <Box 
                            sx={{ 
                              pl: 2, 
                              my: 1, 
                              borderLeft: '3px solid',
                              borderColor: 'primary.main',
                              bgcolor: 'rgba(0, 0, 0, 0.1)',
                              p: 1,
                              borderRadius: 1
                            }}
                          >
                            <Typography variant="body2" color="text.secondary">
                              Forwarded from <strong>{message.referenced_message.author.username}</strong> -{' '}
                              {new Date(message.referenced_message.timestamp).toLocaleString()}
                            </Typography>
                            <Typography component="span" variant="body2" sx={{ display: 'block', mt: 1 }}>
                              {message.referenced_message.content}
                            </Typography>
                            {message.referenced_message.attachments.length > 0 && (
                              <Box sx={{ mt: 1 }}>
                                {message.referenced_message.attachments.map((att) => (
                                  <Button
                                    key={att.url}
                                    href={att.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    size="small"
                                    startIcon={<ImageIcon />}
                                    sx={{ mr: 1, mb: 1 }}
                                  >
                                    {att.filename}
                                  </Button>
                                ))}
                              </Box>
                            )}
                          </Box>
                        )}
                        <Typography
                          component="span"
                          variant="body2"
                          color="text.primary"
                          sx={{ display: 'block', mt: 1 }}
                        >
                          {message.content}
                        </Typography>
                        {message.attachments.length > 0 && (
                          <Box sx={{ mt: 1 }}>
                            {message.attachments.map((att) => (
                              <Button
                                key={att.url}
                                href={att.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                size="small"
                                startIcon={<ImageIcon />}
                                sx={{ mr: 1, mb: 1 }}
                              >
                                {att.filename}
                              </Button>
                            ))}
                          </Box>
                        )}
                      </>
                    }
                  />
                </ListItem>
                {index < messages.length - 1 && <Divider />}
              </Box>
            ))}
          </List>
        </Paper>
      )}
    </Box>
  )
} 