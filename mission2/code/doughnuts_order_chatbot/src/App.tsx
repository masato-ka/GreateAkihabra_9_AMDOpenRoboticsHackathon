import React, { useState, useEffect } from 'react'
import './App.css'
import Logo from './components/Logo'
import RobotIcon from './components/RobotIcon'
import CompleteIcon from './components/CompleteIcon'
import chocolateImage from './img/Chocolate.png'
import strawberryImage from './img/strawberry.png'

type DonutType = 'chocolate' | 'strawberry'

interface Donut {
  id: DonutType
  name: string
  image: string
}

type AppState = 'menu' | 'loading' | 'complete' | 'error'

type LoadingStage = 'WAITING' | 'PUTTING_DONUT' | 'CLOSING_LID' | 'COMPLETE'

interface StatusUpdate {
  type: string
  request_id: string
  stage: LoadingStage
  progress: number
  message: string
}

interface CompletedEvent {
  type: 'completed'
  request_id: string
  result: {
    delivered: boolean
    flavor: string
  }
}

interface DonutWithEnglish extends Donut {
  nameEn: string
}

const DONUTS: DonutWithEnglish[] = [
  { id: 'chocolate', name: 'チョコレートドーナッツ', nameEn: 'Chocolate Donut', image: chocolateImage },
  { id: 'strawberry', name: 'ストロベリードーナッツ', nameEn: 'Strawberry Donut', image: strawberryImage },
]

function App() {
  const [state, setState] = useState<AppState>('menu')
  const [selectedDonut, setSelectedDonut] = useState<DonutType | null>(null)
  const [loadingStatus, setLoadingStatus] = useState<StatusUpdate | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)

  const handleSelectDonut = (donutId: DonutType) => {
    setSelectedDonut(donutId)
  }

  const handleOrder = async () => {
    if (!selectedDonut) return
    
    const donutName = selectedDonut === 'chocolate' ? 'チョコレートドーナッツ' : 'ストロベリードーナッツ'
    
    console.log('========================================')
    console.log('ボタンが押されました:', donutName)
    console.log('送信するflavor:', selectedDonut)
    console.log('========================================')
    
    try {
      const response = await fetch('https://unsupervised-pyrochemically-graig.ngrok-free.dev/orders', {
        method: 'POST',
        headers: {
          'accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          flavor: selectedDonut
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      
      // ターミナルに出力（デバッグ用）
      console.log('========================================')
      console.log('✅ APIリクエスト成功')
      console.log('ボタン:', donutName)
      console.log('レスポンス全体:', JSON.stringify(data, null, 2))
      console.log('レスポンスのキー:', Object.keys(data))
      console.log('data.id:', data.id)
      console.log('data.request_id:', data.request_id)
      console.log('data.order_id:', data.order_id)
      console.log('data.requestId:', data.requestId)
      console.log('========================================')
      
      // リクエストIDを様々な可能性から取得
      const receivedRequestId = 
        data.id || 
        data.request_id || 
        data.order_id || 
        data.requestId ||
        data.requestID ||
        data.requestId ||
        (data.data && (data.data.id || data.data.request_id))
      
      if (receivedRequestId) {
        setRequestId(receivedRequestId)
        setState('loading')
        // 画面上部にスクロール
        window.scrollTo({ top: 0, behavior: 'smooth' })
      } else {
        console.error('リクエストIDが取得できませんでした')
        setState('error')
        // 画面上部にスクロール
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }
    } catch (error: any) {
      console.error('========================================')
      console.error('❌ APIエラーが発生しました')
      console.error('ボタン:', donutName)
      console.error('エラー内容:', error.message || error)
      
      if (error.message?.includes('CORS') || error.message?.includes('Failed to fetch')) {
        console.error('⚠️ CORSエラー: APIサーバー側でCORSヘッダーの設定が必要です')
        console.error('APIサーバー側で以下のヘッダーを設定してください:')
        console.error('  - Access-Control-Allow-Origin: *')
        console.error('  - Access-Control-Allow-Methods: POST, OPTIONS')
        console.error('  - Access-Control-Allow-Headers: Content-Type, accept')
      }
      console.error('========================================')
      
      // エラー画面に遷移
      setState('error')
      // 画面上部にスクロール
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  // SSE接続でステータスを監視
  useEffect(() => {
    if (state === 'loading' && requestId) {
      console.log('========================================')
      console.log('SSE接続を開始します')
      console.log('リクエストID:', requestId)
      console.log('========================================')
      
      const eventSource = new EventSource(
        `https://unsupervised-pyrochemically-graig.ngrok-free.dev/events`
      )
      
      eventSource.onmessage = (event) => {
        try {
          // "data: "プレフィックスを除去
          const dataStr = event.data.startsWith('data: ') 
            ? event.data.substring(6) 
            : event.data
          
          const eventData = JSON.parse(dataStr)
          
          console.log('========================================')
          console.log('📡 イベントを受信')
          console.log('イベントタイプ:', eventData.type)
          console.log('リクエストID:', eventData.request_id)
          console.log('イベント全体:', JSON.stringify(eventData, null, 2))
          console.log('========================================')
          
          // リクエストIDが一致する場合のみ処理
          if (eventData.request_id !== requestId) {
            return
          }
          
          // イベントタイプに応じて処理を分岐
          if (eventData.type === 'completed') {
            const completedEvent = eventData as CompletedEvent
            console.log('========================================')
            console.log('✅ 完了イベントを受信')
            console.log('結果:', completedEvent.result)
            console.log('========================================')
            
            // 完了画面に遷移
            setTimeout(() => {
              setState('complete')
              eventSource.close()
            }, 1000)
          } else if (eventData.type === 'status_update') {
            const statusUpdate = eventData as StatusUpdate
            console.log('========================================')
            console.log('📡 ステータス更新を受信')
            console.log('ステージ:', statusUpdate.stage)
            console.log('進捗:', statusUpdate.progress)
            console.log('メッセージ:', statusUpdate.message)
            console.log('========================================')
            
            // ステータスを更新（完了判定は行わない）
            setLoadingStatus(statusUpdate)
          }
        } catch (error) {
          console.error('イベントのパースエラー:', error)
        }
      }
      
      eventSource.onerror = (error) => {
        console.error('SSE接続エラー:', error)
        eventSource.close()
        // エラー時は一定時間後に完了画面に遷移（フォールバック）
        setTimeout(() => {
          setState('complete')
        }, 5000)
      }
      
      return () => {
        eventSource.close()
      }
    }
  }, [state, requestId])

  const handleReset = () => {
    setState('menu')
    setSelectedDonut(null)
    setLoadingStatus(null)
    setRequestId(null)
  }
  
  // ステージに応じたメッセージを取得
  const getStageMessage = (stage: LoadingStage | null): { en: string; ja: string } => {
    if (!stage) {
      return { en: 'Robot is packing', ja: 'ロボットが詰め込んでいます' }
    }
    
    switch (stage) {
      case 'WAITING':
        return { en: 'Order received', ja: '注文を受け付けました' }
      case 'PUTTING_DONUT':
        return { en: 'Packing donuts', ja: 'ドーナツを詰め込んでいます' }
      case 'CLOSING_LID':
        return { en: 'Closing the box', ja: '箱を閉じています' }
      case 'COMPLETE':
        return { en: 'Complete!', ja: '完了！' }
      default:
        return { en: 'Robot is packing', ja: 'ロボットが詰め込んでいます' }
    }
  }
  
  // ステージに応じた説明文を取得
  const getStageDescription = (stage: LoadingStage | null): { en: string; ja: string } => {
    if (!stage) {
      return { 
        en: 'Great Akihabara Donuts creates the world\'s craziest donuts.',
        ja: '「Great Akihabara Donuts」は、世界一クレイジーなドーナツを生み出します。'
      }
    }
    
    switch (stage) {
      case 'WAITING':
        return { 
          en: 'Great Akihabara Donuts creates the world\'s craziest donuts.',
          ja: '「Great Akihabara Donuts」は、世界一クレイジーなドーナツを生み出します。'
        }
      case 'PUTTING_DONUT':
        return { 
          en: 'Our cutting-edge robot arm packs the finest donuts for you.',
          ja: '最先端のロボットアームが、最高のドーナツを詰め込みます。'
        }
      case 'CLOSING_LID':
        return { 
          en: 'Almost done! The robot is carefully closing the box.',
          ja: 'もうすぐ完了です！ロボットが丁寧に箱を閉じています。'
        }
      default:
        return { 
          en: 'Great Akihabara Donuts creates the world\'s craziest donuts.',
          ja: '「Great Akihabara Donuts」は、世界一クレイジーなドーナツを生み出します。'
        }
    }
  }
  
  const stageMessage = getStageMessage(loadingStatus?.stage || null)
  const stageDescription = getStageDescription(loadingStatus?.stage || null)

  const selectedDonutData = selectedDonut
    ? DONUTS.find((d) => d.id === selectedDonut)
    : null

  return (
    <div className="app">
      {/* ヘッダー */}
      <header className="header">
        <div className="header-content">
          <Logo />
        </div>
      </header>

      {/* メインコンテンツ */}
      <main className="main-content">
        {state === 'menu' && (
          <div className="menu-section">
            <h2 className="menu-title">
              Select Menu
              <span className="menu-title-ja">メニューを選んでください</span>
            </h2>
            <div className="menu-grid">
              {DONUTS.map((donut) => (
                <div
                  key={donut.id}
                  className={`menu-item ${
                    selectedDonut === donut.id ? 'selected' : ''
                  }`}
                  onClick={() => handleSelectDonut(donut.id)}
                >
                  <div className="menu-item-image-wrapper">
                    <img
                      src={donut.image}
                      alt={donut.name}
                      className="menu-item-image"
                    />
                    {selectedDonut === donut.id && (
                      <div className="selected-overlay"></div>
                    )}
                  </div>
                  <div className="menu-item-info">
                    <h3 className="menu-item-name">
                      {donut.nameEn}
                      <span className="menu-item-name-ja">{donut.name}</span>
                    </h3>
                  </div>
                  {selectedDonut === donut.id && (
                    <div className="selected-badge">
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {state === 'loading' && (
          <div className="loading-screen">
            <div className="loading-left">
              <RobotIcon />
            </div>
            <div className="loading-right">
              <h2 className="loading-text">
                {stageMessage.en}
                <span className="loading-text-ja">{stageMessage.ja}</span>
              </h2>
              <p className="loading-description">
                {stageDescription.en}
                <span className="loading-description-ja">{stageDescription.ja}</span>
              </p>
              {loadingStatus?.message && (
                <p className="loading-status-message">
                  {loadingStatus.message}
                </p>
              )}
              <div className="loading-progress-wrapper">
                <div className="loading-progress-container">
                  <div 
                    className="loading-progress-bar"
                    style={{ width: `${(loadingStatus?.progress || 0) * 100}%` }}
                  ></div>
                </div>
                <div className="loading-progress-text">
                  {Math.round((loadingStatus?.progress || 0) * 100)}%
                </div>
              </div>
              <div className="loading-spinner"></div>
            </div>
          </div>
        )}

        {state === 'complete' && (
          <div className="complete-screen">
            <CompleteIcon />
            <h2 className="complete-text">
              Complete!
              <span className="complete-text-ja">完了！</span>
            </h2>
            <p className="complete-message">
              Enjoy your donuts!
              <span className="complete-message-ja">おいしく食べてね</span>
            </p>
            <button className="reset-btn" onClick={handleReset}>
              Order Again
              <span className="reset-btn-ja">もう一度注文する</span>
            </button>
          </div>
        )}

        {state === 'error' && (
          <div className="error-screen">
            <div className="error-icon">⚠️</div>
            <h2 className="error-text">
              Request ID Not Found
              <span className="error-text-ja">リクエストIDが取得できませんでした</span>
            </h2>
            <p className="error-message">
              Unable to process your order. Please try again.
              <span className="error-message-ja">注文を処理できませんでした。もう一度お試しください。</span>
            </p>
            <button className="reset-btn" onClick={handleReset}>
              Back to Menu
              <span className="reset-btn-ja">メニューに戻る</span>
            </button>
          </div>
        )}
      </main>

      {/* フッター */}
      {state === 'menu' && (
        <footer className="footer">
          <div className="footer-content">
            {selectedDonutData ? (
              <>
                <div className="order-info">
                  <div className="order-donut">
                    <img
                      src={selectedDonutData.image}
                      alt={selectedDonutData.name}
                      className="order-donut-image"
                    />
                    <div className="order-details">
                      <p className="order-name">
                        {selectedDonutData.nameEn}
                        <span className="order-name-ja">{selectedDonutData.name}</span>
                      </p>
                    </div>
                  </div>
                </div>
                <button className="checkout-btn" onClick={handleOrder}>
                  Proceed to Checkout
                  <span className="checkout-btn-ja">レジに進む</span>
                </button>
              </>
            ) : (
              <p className="no-selection">
                Please select a menu
                <span className="no-selection-ja">メニューを選択してください</span>
              </p>
            )}
          </div>
        </footer>
      )}
    </div>
  )
}

export default App
